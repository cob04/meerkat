from apps.search.contracts import (
    LOW_STOCK_TOP_N,
    LowStockItem,
    LowStockResult,
    StockBucket,
    StockQuery,
)

LOCATION_BUCKET_SIZE = 50
CATEGORY_BUCKET_SIZE = 30


def build_body(query: StockQuery) -> dict:
    filters = [
        {"term": {"status": "available"}},
        {"range": {"quantity": {"lt": query.threshold}}},
    ]
    if query.location:
        filters.append({"terms": {"location_name.keyword": query.location}})
    if query.category:
        filters.append({"terms": {"product_category": query.category}})

    return {
        "size": LOW_STOCK_TOP_N,
        "track_total_hits": True,
        "sort": [{"quantity": {"order": "asc"}}, {"expiry_date": {"order": "asc"}}],
        "query": {"bool": {"filter": filters}},
        "aggs": {
            "out_of_stock": {"filter": {"term": {"quantity": 0}}},
            "by_location": {
                "terms": {"field": "location_name.keyword", "size": LOCATION_BUCKET_SIZE}
            },
            "by_category": {"terms": {"field": "product_category", "size": CATEGORY_BUCKET_SIZE}},
        },
    }


def parse_response(response: dict, query: StockQuery) -> LowStockResult:
    aggs = response.get("aggregations", {})
    hits = response.get("hits", {})
    items = [
        LowStockItem(
            id=int(hit["_id"]),
            item_name=hit["_source"].get("item_name", ""),
            product_name=hit["_source"].get("product_name"),
            location_name=hit["_source"].get("location_name"),
            category=hit["_source"].get("product_category"),
            quantity=int(hit["_source"].get("quantity", 0)),
            expiry_date=hit["_source"].get("expiry_date"),
        )
        for hit in hits.get("hits", [])
    ]
    return LowStockResult(
        threshold=query.threshold,
        total_items=hits.get("total", {}).get("value", 0),
        out_of_stock=int(aggs.get("out_of_stock", {}).get("doc_count", 0)),
        items=items,
        by_location=_extract_buckets(aggs.get("by_location", {})),
        by_category=_extract_buckets(aggs.get("by_category", {})),
        engine_took_ms=response.get("took", 0),
    )


def _extract_buckets(agg: dict) -> list[StockBucket]:
    return [
        StockBucket(key=str(b["key"]), count=int(b.get("doc_count", 0)))
        for b in agg.get("buckets", [])
        if b.get("key")
    ]
