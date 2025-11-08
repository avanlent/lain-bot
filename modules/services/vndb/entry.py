from __future__ import annotations

from typing import Optional

from ..anilist.enums import ChangeKind, Status
from ..models.change import Change
from ..models.entry import ListEntry, Specs, field
from ..models.data import Image


def _format_title(self: VnEntry) -> str:
    title = self['title'] or 'Unknown VN'
    link = self._link()
    if link:
        return f"[{title}]({link})"
    return title


def _status_consumer(self: VnEntry, old: str, new: str) -> Optional[Change]:
    if old == new:
        return None

    old_label = old if old else Status.UNKNOWN
    new_label = new if new else Status.UNKNOWN
    return Change(
        ChangeKind.STATUS,
        old_label,
        new_label,
        f"status of {_format_title(self)} set to {new_label}",
    )


def _vote_consumer(self: VnEntry, old: Optional[int], new: Optional[int]) -> Optional[Change]:
    if old == new:
        return None

    target = _format_title(self)
    if not old:
        return Change(ChangeKind.SCORE, old, new, f"score for {target} set to {new}")
    return Change(ChangeKind.SCORE, old, new, f"score for {target} changed: {old} ➔ {new}")


class VnEntry(ListEntry):
    specs = Specs(
        DATA_FIELDS=[
            field('id', '', concealed=True),
            field('attributes', 0),
            field('title', ''),
            field('lastmod', 0),
            field('image_url', '', concealed=True),
            field('image_nsfw', False, concealed=True),
        ],
        DYNAMIC_FIELDS=[
            field('vote', None, _vote_consumer),
            field('status', Status.UNKNOWN, _status_consumer),
        ],
    )

    def images(self):
        url = self['image_url']
        if not url:
            return []
        return [Image(narrow=url, wide=url, nsfw=bool(self['image_nsfw']))]

    def _link(self) -> Optional[str]:
        vid = str(self['id']) if self['id'] is not None else ''
        if not vid:
            return None
        if vid.startswith('v'):
            return f"https://vndb.org/{vid}"
        return f"https://vndb.org/v{vid}"

