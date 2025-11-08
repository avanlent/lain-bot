import re
from typing import Dict

from modules.core.resources import Resources

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
		try:
			async with Resources.session.post(f'{API_BASE}/vn', json=payload, raise_for_status=True) as resp:
				data = await resp.json()
		except Exception:
			async with Resources.session.post(f'{API_BASE}/vn', json=payload) as resp:
				text = await resp.text()
				raise RuntimeError(f'VNDB kana request failed: {resp.status} {text}') from None
		return data

	async def quote(self):
		async with Resources.session.get('https://vndb.org/', headers={'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_14_4) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/75.0.3770.100 Safari/537.36'}) as resp:
			if resp.status != 200:
				raise Exception("Bad fetch")
			html = await resp.read()
			html = html.decode('utf-8')
		
		srch = re.search(r'"<a href="/(v\d+)">(.*)</a>&quot;', html)
		quote = srch.group(2)
		vid = srch.group(1)

		async with Resources.session.post(f'{API_BASE}/vn', json={'filters': ['id', '=', vid], 'fields': 'title, image.url'}) as resp:
			if resp.status != 200:
				raise Exception("Bad fetch")
			data = await resp.json()
		
		item = data['results'][0]

		return {'quote': quote, 'title': item['title'], 'cover': item['image']['url'], 'id': item['id']}

