from apps.search.contracts import (
    DEAD_STOCK_TOP_N,
    TOP_MOVERS_N,
    DeadStockRow,
    MoverRow,
    ThroughputPoint,
    TurnoverQuery,
)

INSTOCK_PRODUCT_LIMIT = 1000
DISPENSED_PRODUCT_LIMIT = 1000
THROUGHPUT_WEEKS = 8


def build_movements_body(query: TurnoverQuery) -> dict:
    """Aggregations over the stock-movements index."""
    window = f"now-{query.window_days}d/d"
    dead_window = f"now-{query.dead_window_days}d/d"
    throughput_from = f"now-{THROUGHPUT_WEEKS}w/d"
    return {
        "size": 0,
        "query": {"match_all": {}},
        "aggs": {
            "dispensed_units": {
                "filter": {
                    "bool": {
                        "filter": [
                            {"term": {"movement_type": "dispensed"}},
                            {"range": {"created_at": {"gte": window}}},
                        ]
                    }
                },
                "aggs": {"q": {"sum": {"field": "quantity"}}},
            },
            "received_units": {
                "filter": {
                    "bool": {
                        "filter": [
                            {"term": {"movement_type": "received"}},
                            {"range": {"created_at": {"gte": window}}},
                        ]
                    }
                },
                "aggs": {"q": {"sum": {"field": "quantity"}}},
            },
            "throughput": {
                "filter": {"range": {"created_at": {"gte": throughput_from}}},
                "aggs": {
                    "by_week": {
                        "date_histogram": {
                            "field": "created_at",
                            "calendar_interval": "week",
                            "format": "yyyy-MM-dd",
                            "min_doc_count": 0,
                            "extended_bounds": {"min": throughput_from, "max": "now/d"},
                        },
                        "aggs": {
                            "dispensed": {
                                "filter": {"term": {"movement_type": "dispensed"}},
                                "aggs": {"q": {"sum": {"field": "quantity"}}},
                            },
                            "received": {
                                "filter": {"term": {"movement_type": "received"}},
                                "aggs": {"q": {"sum": {"field": "quantity"}}},
                            },
                        },
                    }
                },
            },
            "top_movers": {
                "filter": {
                    "bool": {
                        "filter": [
                            {"term": {"movement_type": "dispensed"}},
                            {"range": {"created_at": {"gte": window}}},
                        ]
                    }
                },
                "aggs": {
                    "products": {
                        "terms": {
                            "field": "product_name.keyword",
                            "size": TOP_MOVERS_N,
                            "order": {"units": "desc"},
                        },
                        "aggs": {"units": {"sum": {"field": "quantity"}}},
                    }
                },
            },
            "dispensed_products": {
                "filter": {
                    "bool": {
                        "filter": [
                            {"term": {"movement_type": "dispensed"}},
                            {"range": {"created_at": {"gte": dead_window}}},
                        ]
                    }
                },
                "aggs": {
                    "products": {
                        "terms": {"field": "product_name.keyword", "size": DISPENSED_PRODUCT_LIMIT}
                    }
                },
            },
        },
    }


def parse_movements(response: dict) -> dict:
    aggs = response.get("aggregations", {})

    def filt_sum(name: str) -> int:
        return int(aggs.get(name, {}).get("q", {}).get("value") or 0)

    weeks = aggs.get("throughput", {}).get("by_week", {}).get("buckets", [])
    throughput = [
        ThroughputPoint(
            period=w.get("key_as_string", ""),
            dispensed=int(w.get("dispensed", {}).get("q", {}).get("value") or 0),
            received=int(w.get("received", {}).get("q", {}).get("value") or 0),
        )
        for w in weeks
    ]

    movers = aggs.get("top_movers", {}).get("products", {}).get("buckets", [])
    top_movers = [
        MoverRow(product=str(b["key"]), units=int(b.get("units", {}).get("value") or 0))
        for b in movers
        if b.get("key")
    ]

    dispensed_products = {
        str(b["key"])
        for b in aggs.get("dispensed_products", {}).get("products", {}).get("buckets", [])
        if b.get("key")
    }

    return {
        "dispensed_units": filt_sum("dispensed_units"),
        "received_units": filt_sum("received_units"),
        "throughput": throughput,
        "top_movers": top_movers,
        "dispensed_products": dispensed_products,
        "engine_took_ms": response.get("took", 0),
    }


def build_instock_body() -> dict:
    """Products with available stock, from the inventory index."""
    return {
        "size": 0,
        "query": {
            "bool": {
                "filter": [{"term": {"status": "available"}}, {"range": {"quantity": {"gt": 0}}}]
            }
        },
        "aggs": {
            "products": {
                "terms": {"field": "product_name.keyword", "size": INSTOCK_PRODUCT_LIMIT},
                "aggs": {
                    "units": {"sum": {"field": "quantity"}},
                    "value": {"sum": {"field": "line_value"}},
                },
            }
        },
    }


def dead_stock(
    instock_response: dict, dispensed_products: set[str]
) -> tuple[list[DeadStockRow], float]:
    buckets = instock_response.get("aggregations", {}).get("products", {}).get("buckets", [])
    rows = [
        DeadStockRow(
            product=str(b["key"]),
            units=int(b.get("units", {}).get("value") or 0),
            value=float(b.get("value", {}).get("value") or 0.0),
        )
        for b in buckets
        if b.get("key") and str(b["key"]) not in dispensed_products
    ]
    rows.sort(key=lambda r: r.value, reverse=True)
    total_value = sum(r.value for r in rows)
    return rows[:DEAD_STOCK_TOP_N], total_value
