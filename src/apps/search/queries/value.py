from apps.search.contracts import ValueBucket, ValueQuery, ValueResult

BUCKET_SIZE = 50


def _value_subaggs() -> dict:
    return {
        "value": {"sum": {"field": "line_value"}},
        "units": {"sum": {"field": "quantity"}},
    }


def build_body(query: ValueQuery) -> dict:
    filters = []
    if query.location:
        filters.append({"terms": {"location_name.keyword": query.location}})
    if query.category:
        filters.append({"terms": {"product_category": query.category}})

    return {
        "size": 0,
        "track_total_hits": True,
        "query": {"bool": {"filter": filters}} if filters else {"match_all": {}},
        "aggs": {
            "total_value": {"sum": {"field": "line_value"}},
            "total_quantity": {"sum": {"field": "quantity"}},
            "by_location": {
                "terms": {"field": "location_name.keyword", "size": BUCKET_SIZE},
                "aggs": _value_subaggs(),
            },
            "by_category": {
                "terms": {"field": "product_category", "size": BUCKET_SIZE},
                "aggs": _value_subaggs(),
            },
            "by_manufacturer": {
                "terms": {"field": "drug_manufacturer.keyword", "size": BUCKET_SIZE},
                "aggs": _value_subaggs(),
            },
        },
    }


def parse_response(response: dict, query: ValueQuery) -> ValueResult:
    aggs = response.get("aggregations", {})
    hits = response.get("hits", {})
    return ValueResult(
        total_value=float(aggs.get("total_value", {}).get("value") or 0.0),
        total_quantity=int(aggs.get("total_quantity", {}).get("value") or 0),
        total_items=hits.get("total", {}).get("value", 0),
        by_location=_buckets(aggs.get("by_location", {})),
        by_category=_buckets(aggs.get("by_category", {})),
        by_manufacturer=_buckets(aggs.get("by_manufacturer", {})),
        engine_took_ms=response.get("took", 0),
    )


def _buckets(agg: dict) -> list[ValueBucket]:
    buckets = []
    for b in agg.get("buckets", []):
        if not b.get("key"):
            continue
        buckets.append(
            ValueBucket(
                key=str(b["key"]),
                value=float(b.get("value", {}).get("value") or 0.0),
                quantity=int(b.get("units", {}).get("value") or 0),
                items=int(b.get("doc_count", 0)),
            )
        )
    return buckets
