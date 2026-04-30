from apps.search.contracts import (
    DEFAULT_PAGE_SIZE,
    FacetBreakdown,
    InventoryDoc,
    InventoryQuery,
    InventoryResults,
)

EXPIRY_BUCKET_RANGES = {
    "expired": {"lt": "now/d"},
    "30d": {"gte": "now/d", "lt": "now+30d/d"},
    "90d": {"gte": "now+30d/d", "lt": "now+90d/d"},
    "90plus": {"gte": "now+90d/d"},
}

SEARCH_FIELDS = [
    "product_name^3",
    "drug_brand_name^3",
    "drug_inn_name^2",
    "item_name^2",
    "drug_manufacturer",
    "batch_number",
]

FACET_FIELDS = {
    "status": "status",
    "location": "location_name.keyword",
    "category": "product_category",
}

FACET_BUCKET_SIZE = 50


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

    expiry_clause = expiry_filter(query.expiry_bucket)
    if expiry_clause:
        scoped_query = {"bool": {"must": [match_query], "filter": [expiry_clause]}}
    else:
        scoped_query = match_query

    body = {
        "from": offset,
        "size": page_size,
        "query": scoped_query,
        "sort": _build_sort(query.sort),
        "track_total_hits": True,
        "aggs": _build_aggs(query),
    }

    post_filter = _build_post_filter(query)
    if post_filter is not None:
        body["post_filter"] = post_filter

    return body


def expiry_filter(bucket: str | None) -> dict | None:
    if not bucket or bucket not in EXPIRY_BUCKET_RANGES:
        return None
    return {"range": {"expiry_date": EXPIRY_BUCKET_RANGES[bucket]}}


def _build_sort(sort: str) -> list:
    if sort == "_score":
        return ["_score", {"updated_at": {"order": "desc"}}]
    field = sort.lstrip("-")
    order = "desc" if sort.startswith("-") else "asc"
    return [{field: {"order": order}}]


def _selections(query: InventoryQuery) -> dict[str, list[str]]:
    return {
        "status": list(query.status),
        "location": list(query.location),
        "category": list(query.category),
    }


def _filter_clauses(query: InventoryQuery, exclude: str | None = None) -> list[dict]:
    clauses = []
    for facet, values in _selections(query).items():
        if facet == exclude or not values:
            continue
        clauses.append({"terms": {FACET_FIELDS[facet]: values}})
    return clauses


def _build_post_filter(query: InventoryQuery) -> dict | None:
    clauses = _filter_clauses(query)
    if not clauses:
        return None
    return {"bool": {"filter": clauses}}


def _build_aggs(query: InventoryQuery) -> dict:
    aggs = {}
    for facet, field_name in FACET_FIELDS.items():
        other_filters = _filter_clauses(query, exclude=facet)
        aggs[facet] = {
            "filter": {"bool": {"filter": other_filters}},
            "aggs": {"buckets": {"terms": {"field": field_name, "size": FACET_BUCKET_SIZE}}},
        }
    return aggs


def parse_response(response: dict, query: InventoryQuery) -> InventoryResults:
    hits = response.get("hits", {})
    total = hits.get("total", {}).get("value", 0)
    items = [InventoryDoc.from_hit(hit) for hit in hits.get("hits", [])]
    aggs = response.get("aggregations", {})
    return InventoryResults(
        items=items,
        total=total,
        page=max(query.page, 1),
        page_size=query.page_size or DEFAULT_PAGE_SIZE,
        engine_took_ms=response.get("took", 0),
        facets=FacetBreakdown(
            status=_extract_buckets(aggs, "status"),
            location=_extract_buckets(aggs, "location"),
            category=_extract_buckets(aggs, "category"),
        ),
    )


def _extract_buckets(aggs: dict, name: str) -> dict[str, int]:
    facet = aggs.get(name, {})
    buckets = facet.get("buckets", {}).get("buckets", [])
    return {bucket["key"]: bucket["doc_count"] for bucket in buckets}
