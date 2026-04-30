from apps.search.contracts import AvailabilityQuery, AvailabilityResult, LocationStock

LOCATION_BUCKET_SIZE = 100


def build_body(query: AvailabilityQuery, origin: dict | None = None) -> dict:
    must = []
    if query.product_id is not None:
        must.append({"term": {"product_id": query.product_id}})
    if query.drug_id is not None:
        must.append({"term": {"drug_id": query.drug_id}})

    filters = [
        {"term": {"status": "available"}},
        {"range": {"quantity": {"gt": 0}}},
    ]
    if origin and query.max_distance_km:
        filters.append(
            {
                "geo_distance": {
                    "distance": f"{query.max_distance_km}km",
                    "location_geo": origin,
                }
            }
        )

    return {
        "size": 0,
        "track_total_hits": True,
        "query": {"bool": {"must": must, "filter": filters}},
        "aggs": {
            "by_location": {
                "terms": {
                    "field": "location_id",
                    "size": LOCATION_BUCKET_SIZE,
                    "order": _bucket_order(query.sort),
                },
                "aggs": {
                    "location_name": {"terms": {"field": "location_name.keyword", "size": 1}},
                    "total_quantity": {"sum": {"field": "quantity"}},
                },
            },
            "network_quantity": {"sum": {"field": "quantity"}},
        },
    }


def _bucket_order(sort: str) -> dict:
    if sort == "-quantity":
        return {"total_quantity": "desc"}
    return {"_count": "desc"}


def parse_response(response: dict, query: AvailabilityQuery) -> AvailabilityResult:
    aggs = response.get("aggregations", {})
    buckets = aggs.get("by_location", {}).get("buckets", [])
    by_location = [
        LocationStock(
            location_id=int(bucket["key"]),
            location_name=_first_bucket_key(bucket.get("location_name", {})),
            quantity=int(bucket.get("total_quantity", {}).get("value", 0)),
            item_count=int(bucket.get("doc_count", 0)),
        )
        for bucket in buckets
    ]
    return AvailabilityResult(
        product_id=query.product_id,
        drug_id=query.drug_id,
        total_quantity=int(aggs.get("network_quantity", {}).get("value", 0)),
        total_items=response.get("hits", {}).get("total", {}).get("value", 0),
        by_location=by_location,
        engine_took_ms=response.get("took", 0),
    )


def _first_bucket_key(agg: dict) -> str:
    buckets = agg.get("buckets", [])
    if not buckets:
        return ""
    return str(buckets[0].get("key", ""))
