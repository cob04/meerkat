from apps.search import client
from apps.search.contracts import InventoryQuery, InventoryResults
from apps.search.queries import search as search_query


def search_inventory(query: InventoryQuery) -> InventoryResults:
    body = search_query.build_body(query)
    response = client.search(body)
    return search_query.parse_response(response, query)
