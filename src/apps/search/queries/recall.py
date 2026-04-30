from apps.search.contracts import (
    RECALL_TOP_N,
    RecallBucket,
    RecallImpact,
    RecallMatch,
    RecallQuery,
)

LOCATION_BUCKET_SIZE = 100


def build_body(query: RecallQuery) -> dict:
    must = []
    if query.manufacturer:
        must.append({"match_phrase": {"drug_manufacturer": query.manufacturer}})
    if query.batch_pattern:
        must.append({"wildcard": {"batch_number": _to_wildcard(query.batch_pattern)}})
    if query.drug_id is not None:
        must.append({"term": {"drug_id": query.drug_id}})

    range_clause = {}
    if query.created_from:
        range_clause["gte"] = query.created_from
    if query.created_to:
        range_clause["lte"] = query.created_to
    if range_clause:
        must.append({"range": {"created_at": range_clause}})

    return {
        "size": RECALL_TOP_N,
        "track_total_hits": True,
        "sort": [{"created_at": {"order": "desc"}}],
        "query": {"bool": {"must": must}} if must else {"match_all": {}},
        "aggs": {
            "by_location": {
                "terms": {
                    "field": "location_name.keyword",
                    "size": LOCATION_BUCKET_SIZE,
                },
                "aggs": {"total_quantity": {"sum": {"field": "quantity"}}},
            },
            "network_quantity": {"sum": {"field": "quantity"}},
        },
    }


def _to_wildcard(pattern: str) -> str:
    return pattern if "*" in pattern or "?" in pattern else f"*{pattern}*"


def parse_response(response: dict) -> RecallImpact:
    aggs = response.get("aggregations", {})
    hits = response.get("hits", {})
    matches = [_to_match(hit) for hit in hits.get("hits", [])]
    by_location = [
        RecallBucket(
            location_name=str(b["key"]),
            item_count=int(b.get("doc_count", 0)),
            quantity=int(b.get("total_quantity", {}).get("value", 0)),
        )
        for b in aggs.get("by_location", {}).get("buckets", [])
        if b.get("key")
    ]
    return RecallImpact(
        total_items=hits.get("total", {}).get("value", 0),
        total_quantity=int(aggs.get("network_quantity", {}).get("value", 0)),
        matches=matches,
        by_location=by_location,
        engine_took_ms=response.get("took", 0),
    )


def _to_match(hit: dict) -> RecallMatch:
    source = hit.get("_source", {})
    return RecallMatch(
        id=int(hit["_id"]),
        item_name=source.get("item_name", ""),
        product_name=source.get("product_name"),
        drug_inn_name=source.get("drug_inn_name"),
        manufacturer=source.get("drug_manufacturer"),
        batch_number=source.get("batch_number", ""),
        location_name=source.get("location_name"),
        quantity=int(source.get("quantity", 0)),
        status=source.get("status", ""),
        expiry_date=source.get("expiry_date"),
    )
