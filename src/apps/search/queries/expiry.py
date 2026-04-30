from apps.search.contracts import (
    EXPIRY_BUCKET_LABELS,
    EXPIRY_BUCKETS,
    CategoryExpiry,
    ExpiryBucket,
    ExpiryQuery,
    ExpiryRollup,
    LocationExpiry,
)

LOCATION_BUCKET_SIZE = 50
CATEGORY_BUCKET_SIZE = 30

DATE_RANGES = [
    {"key": "expired", "to": "now/d"},
    {"key": "30d", "from": "now/d", "to": "now+30d/d"},
    {"key": "90d", "from": "now+30d/d", "to": "now+90d/d"},
    {"key": "90plus", "from": "now+90d/d"},
]


def build_body(query: ExpiryQuery) -> dict:
    filters = []
    if query.location:
        filters.append({"terms": {"location_name.keyword": query.location}})
    if query.category:
        filters.append({"terms": {"product_category": query.category}})

    return {
        "size": 0,
        "track_total_hits": True,
        "query": {
            "bool": {
                "must": [{"exists": {"field": "expiry_date"}}],
                "filter": filters,
            }
        },
        "aggs": {
            "by_bucket": _date_range_agg(),
            "by_location": {
                "terms": {
                    "field": "location_name.keyword",
                    "size": LOCATION_BUCKET_SIZE,
                },
                "aggs": {"by_bucket": _date_range_agg()},
            },
            "by_category": {
                "terms": {
                    "field": "product_category",
                    "size": CATEGORY_BUCKET_SIZE,
                },
                "aggs": {"by_bucket": _date_range_agg()},
            },
        },
    }


def _date_range_agg() -> dict:
    return {"date_range": {"field": "expiry_date", "ranges": DATE_RANGES}}


def parse_response(response: dict) -> ExpiryRollup:
    aggs = response.get("aggregations", {})
    return ExpiryRollup(
        total_items=response.get("hits", {}).get("total", {}).get("value", 0),
        buckets=_extract_buckets(aggs.get("by_bucket", {})),
        by_location=[
            LocationExpiry(
                location_name=str(parent["key"]),
                total=int(parent.get("doc_count", 0)),
                buckets=_extract_buckets(parent.get("by_bucket", {})),
            )
            for parent in aggs.get("by_location", {}).get("buckets", [])
        ],
        by_category=[
            CategoryExpiry(
                category=str(parent["key"]),
                total=int(parent.get("doc_count", 0)),
                buckets=_extract_buckets(parent.get("by_bucket", {})),
            )
            for parent in aggs.get("by_category", {}).get("buckets", [])
            if parent.get("key")
        ],
        engine_took_ms=response.get("took", 0),
    )


def _extract_buckets(date_range_agg: dict) -> list[ExpiryBucket]:
    raw = date_range_agg.get("buckets", [])
    items = {b["key"]: int(b.get("doc_count", 0)) for b in raw}
    return [
        ExpiryBucket(key=key, label=EXPIRY_BUCKET_LABELS[key], count=items.get(key, 0))
        for key in EXPIRY_BUCKETS
    ]
