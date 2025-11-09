import re, html
from typing import Dict

from aiohttp import ClientResponseError

from modules.core.resources import Resources
from modules.services.vndb_ratelimit import RateLimitError, parse_retry_after

API_BASE = 'https://api.vndb.org/kana'

VN_FIELDS = ', '.join([
	'id',
	'title',
	'aliases',
	'released',
	'length',
	'platforms',
	'languages',
	'description',
	'rating',
	'votecount',
	'popularity',
	'image.url',
	'image.sexual',
	'image.violence',
	'screenshots.url',
	'screenshots.thumbnail',
	'screenshots.sexual',
	'screenshots.violence',
])

class VndbSearch:
	def __init__(self):
		pass

	async def vn(self, title: str, limit: int = 5) -> Dict:
		payload = {
			'filters': ['search', '=', title],
			'fields': VN_FIELDS,
			'sort': 'searchrank',
			'results': limit,
		}
		await Resources.vndb_rate_limiter.consume(for_sync=False)
		try:
			async with Resources.session.post(f'{API_BASE}/vn', json=payload, raise_for_status=True) as resp:
				data = await resp.json()
		except ClientResponseError as exc:
			if exc.status == 429:
				retry_after = parse_retry_after(exc.headers.get('Retry-After'))
				retry_after = await Resources.vndb_rate_limiter.mark_limited(retry_after)
				raise RateLimitError(retry_after) from exc
			raise
		except Exception:
			async with Resources.session.post(f'{API_BASE}/vn', json=payload) as resp:
				text = await resp.text()
				raise RuntimeError(f'VNDB kana request failed: {resp.status} {text}') from None
		return data

	async def quote(self):
		payload = {
			"fields": "quote,vn{id,title,image.url},character{id,name}",
			"filters": ["random", "=", 1],
		}

		await Resources.vndb_rate_limiter.consume(for_sync=False)
		try:
			async with Resources.session.post(f'{API_BASE}/quote', json=payload, raise_for_status=True) as resp:
				data = await resp.json()
		except ClientResponseError as exc:
			if exc.status == 429:
				retry_after = parse_retry_after(exc.headers.get('Retry-After'))
				retry_after = await Resources.vndb_rate_limiter.mark_limited(retry_after)
				raise RateLimitError(retry_after) from exc
			raise

		results = data.get('results') or []
		if not results:
			raise RuntimeError("VNDB quote request returned no results")

		item = results[0]
		vn_data = item.get('vn') or {}
		image_data = vn_data.get('image') or {}
		return {
			'quote': item.get('quote', ''),
			'title': vn_data.get('title', 'Unknown'),
			'cover': image_data.get('url') or '',
			'id': vn_data.get('id'),
			'character': item.get('character'),
		}

