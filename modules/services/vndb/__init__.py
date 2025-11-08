from .profile import VndbProfile
from .entry import VnEntry
from .query import VndbQuery


class Description:
    label = 'vndb'
    lists = ['vn']
    profile = VndbProfile
    query = VndbQuery
    link_fn = lambda id: f"https://vndb.org/{id if str(id).startswith('u') else f'u{id}'}"
    time_between_queries = 30

