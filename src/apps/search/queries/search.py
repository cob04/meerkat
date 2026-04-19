from apps.search.contracts import (
    DEFAULT_PAGE_SIZE,
    InventoryDoc,
    InventoryQuery,
    InventoryResults,
)

SEARCH_FIELDS = [
    "product_name^3",
    "drug_brand_name^3",
    "drug_inn_name^2",
    "item_name^2",
    "drug_manufacturer",
    "batch_number",
]


def build_body(query: InventoryQuery) -> dict:
    page_size = query.page_size or DEFAULT_PAGE_SIZE
    page = max(query.page, 1)
    offset = (page - 1) * page_size

    if query.q:
        match_query = {
            "multi_match": {
                "query": query.q,
                "fields": SEARCH_FIELDS,
                "fuzziness": "AUTO",
                "operator": "and",
            }
        }
    else:
        match_query = {"match_all": {}}

    return {
        "from": offset,
        "size": page_size,
        "query": match_query,
        "sort": _build_sort(query.sort),
        "track_total_hits": True,
    }


def _build_sort(sort: str) -> list:
    if sort == "_score":
        return ["_score", {"updated_at": {"order": "desc"}}]
    field = sort.lstrip("-")
    order = "desc" if sort.startswith("-") else "asc"
    return [{field: {"order": order}}]


def parse_response(response: dict, query: InventoryQuery) -> InventoryResults:
    hits = response.get("hits", {})
    total = hits.get("total", {}).get("value", 0)
    items = [InventoryDoc.from_hit(hit) for hit in hits.get("hits", [])]
    return InventoryResults(
        items=items,
        total=total,
        page=max(query.page, 1),
        page_size=query.page_size or DEFAULT_PAGE_SIZE,
        engine_took_ms=response.get("took", 0),
    )
