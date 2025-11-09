from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Dict, List

if TYPE_CHECKING:
    from ..models.user import User

from aiohttp import ClientResponseError

from modules.core.resources import Resources
from ..models.query import Query, user_id
from ..models.data import FetchData, QueryResult, ResultStatus, UserSearch
from ..models.entry import ListEntry
from ..anilist.enums import Status
from .entry import VnEntry
from .profile import VndbProfile
from modules.services.vndb_ratelimit import RateLimitError, SyncBudgetError, parse_retry_after

logger = logging.getLogger(__name__)

API_BASE = 'https://api.vndb.org/kana'

VN_FIELDS = 'id, vote, lastmod, labels.id, labels.label, vn.title, vn.image.url, vn.image.sexual, vn.image.violence'

LABEL_STATUS_MAP = {
    1: Status.CURRENT,    # Playing
    2: Status.COMPLETED,  # Finished
    3: Status.PAUSED,     # Stalled
    4: Status.DROPPED,    # Dropped
    5: Status.PLANNING,   # Wishlist
}


class VndbQuery(Query):
    MAX_USERS_PER_QUERY = 5

    async def find(self, username: str) -> UserSearch:
        if not username:
            return UserSearch(status=ResultStatus.ERROR, data='No username provided')

        try:
            async with Resources.syncer_session.get(
                f'{API_BASE}/user',
                params={'q': username},
                raise_for_status=True,
            ) as resp:
                data = await resp.json()
        except Exception as exc:
            logger.exception('VNDB user lookup failed')
            return UserSearch(status=ResultStatus.ERROR, data=str(exc))

        results: List[Dict] = []
        if isinstance(data, dict):
            if 'results' in data:
                results = data['results']
            elif 'items' in data:
                results = data['items']
            else:
                results = [
                    entry for entry in data.values()
                    if isinstance(entry, dict) and entry is not None
                ]
        elif isinstance(data, list):
            results = data

        if not results:
            return UserSearch(status=ResultStatus.NOTFOUND, data='Could not find VNDB user')

        user = results[0]
        service_id = user.get('id')
        name = user.get('username', username)

        profile = VndbProfile(name=name)

        return UserSearch(
            status=ResultStatus.OK,
            id=service_id,
            image=profile.avatar,
            link=f"https://vndb.org/{service_id if str(service_id).startswith('u') else f'u{service_id}'}",
            data=FetchData(
                lists={'vn': QueryResult(status=ResultStatus.SKIP, data=None)},
                profile=QueryResult(status=ResultStatus.OK, data=profile),
            ),
        )

    async def fetch(self, users: List['User'] = [], tries: int = 3) -> Dict[user_id, FetchData]:
        if not users:
            self.deferred_users = []
            return {}

        self.deferred_users: List['User'] = []

        results: Dict[user_id, FetchData] = {}
        for index, user in enumerate(users):
            entries: List[ListEntry] = []
            try:
                entries = await self._fetch_user_entries(user.service_id)
            except SyncBudgetError as exc:
                logger.info(
                    "VNDB sync budget reached; pausing sync for %.2f seconds",
                    exc.retry_after,
                )
                self.deferred_users = users[index:]
                break
            except RateLimitError as exc:
                logger.warning(
                    "VNDB API hard rate limit reached; retry after %.2f seconds",
                    exc.retry_after,
                )
                self.deferred_users = users[index:]
                break
            except Exception as exc:
                logger.exception('VNDB fetch failed for user %s', user.service_id)
                results[user._id] = FetchData(
                    lists={'vn': QueryResult(status=ResultStatus.ERROR, data=str(exc))},
                    profile=QueryResult(status=ResultStatus.OK, data=user.profile),
                )
                continue

            results[user._id] = FetchData(
                lists={'vn': QueryResult(status=ResultStatus.OK, data=entries)},
                profile=QueryResult(status=ResultStatus.OK, data=user.profile),
            )

        return results

    async def _fetch_user_entries(self, service_id: str) -> List[VnEntry]:
        page = 1
        entries: List[VnEntry] = []

        while True:
            payload = {
                'user': service_id,
                'fields': VN_FIELDS,
                'page': page,
                'results': 100,
            }

            await Resources.vndb_rate_limiter.consume(for_sync=True)
            try:
                async with Resources.syncer_session.post(f'{API_BASE}/ulist', json=payload, raise_for_status=True) as resp:
                    data = await resp.json()
            except ClientResponseError as exc:
                if exc.status == 429:
                    retry_after = parse_retry_after(exc.headers.get('Retry-After'))
                    retry_after = await Resources.vndb_rate_limiter.mark_limited(retry_after)
                    raise RateLimitError(retry_after) from exc
                raise

            for item in data.get('results', []):
                entry = self._map_entry(item)
                entries.append(entry)

            if not data.get('more'):
                break

            page += 1

        return entries

    def _map_entry(self, item: Dict) -> VnEntry:
        entry = VnEntry()
        entry['id'] = item.get('id', '')
        entry['title'] = item.get('vn', {}).get('title', 'Unknown VN')
        entry['lastmod'] = item.get('lastmod', 0)
        entry['vote'] = item.get('vote')
        entry['status'] = self._determine_status(item.get('labels', []))
        vn_data = item.get('vn', {}) or {}
        image_data = vn_data.get('image') or {}
        entry['image_url'] = image_data.get('url') or ''
        entry['image_nsfw'] = bool(
            (image_data.get('sexual') or 0) >= 1.5 or
            (image_data.get('violence') or 0) >= 1.5
        )
        entry['attributes'] = 0
        return entry

    def _determine_status(self, labels: List[Dict]) -> str:
        for label in labels:
            label_id = label.get('id')
            label_name = (label.get('label') or '').lower()
            if label_id == 1 or 'current' in label_name or 'playing' in label_name:
                return Status.CURRENT

        for label in labels:
            label_id = label.get('id')
            if label_id in LABEL_STATUS_MAP:
                return LABEL_STATUS_MAP[label_id]
            label_name = (label.get('label') or '').lower()
            if 'play' in label_name:
                return Status.CURRENT
            if 'finish' in label_name or 'complete' in label_name:
                return Status.COMPLETED
            if 'stall' in label_name or 'hold' in label_name:
                return Status.PAUSED
            if 'drop' in label_name:
                return Status.DROPPED
            if 'wish' in label_name or 'plan' in label_name:
                return Status.PLANNING
        return Status.UNKNOWN

    def _sync_budget_response(self, user: 'User') -> FetchData:
        message = (
            "VNDB sync temporarily paused to preserve API quota. "
            "Sync will resume automatically once the cooldown ends."
        )
        return FetchData(
            lists={'vn': QueryResult(status=ResultStatus.ERROR, data=message)},
            profile=QueryResult(status=ResultStatus.OK, data=user.profile),
        )

    def _hard_limit_response(self, user: 'User', retry_after: float) -> FetchData:
        message = (
            "VNDB sync hit the API rate limit. "
            f"Will retry after {max(1, int(retry_after))} seconds."
        )
        return FetchData(
            lists={'vn': QueryResult(status=ResultStatus.ERROR, data=message)},
            profile=QueryResult(status=ResultStatus.OK, data=user.profile),
        )

