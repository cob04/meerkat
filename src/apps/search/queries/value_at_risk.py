from apps.search.contracts import (
    ForecastPoint,
    ValueAtRiskQuery,
    ValueAtRiskResult,
    ValueBucket,
)

BUCKET_SIZE = 50


def _available_in(gte: str, lte: str | None = None) -> dict:
    rng = {"gte": gte}
    if lte:
        rng["lte"] = lte
    return {
        "bool": {
            "filter": [
                {"term": {"status": "available"}},
                {"range": {"expiry_date": rng}},
            ]
        }
    }


def _value_terms(field: str) -> dict:
    return {
        "terms": {"field": field, "size": BUCKET_SIZE},
        "aggs": {
            "value": {"sum": {"field": "line_value"}},
            "units": {"sum": {"field": "quantity"}},
        },
    }


def build_body(query: ValueAtRiskQuery) -> dict:
    horizon = f"now+{query.forecast_months}M/d"
    return {
        "size": 0,
        "query": {"match_all": {}},
        "aggs": {
            "buckets": {
                "date_range": {
                    "field": "expiry_date",
                    "ranges": [
                        {"key": "expired", "to": "now/d"},
                        {"key": "30d", "from": "now/d", "to": "now+30d/d"},
                        {"key": "90d", "from": "now/d", "to": "now+90d/d"},
                    ],
                },
                "aggs": {"value": {"sum": {"field": "line_value"}}},
            },
            "forecast": {
                "filter": _available_in("now/d", horizon),
                "aggs": {
                    "by_month": {
                        "date_histogram": {
                            "field": "expiry_date",
                            "calendar_interval": "month",
                            "format": "yyyy-MM",
                            "min_doc_count": 0,
                            "extended_bounds": {"min": "now/d", "max": horizon},
                        },
                        "aggs": {"value": {"sum": {"field": "line_value"}}},
                    }
                },
            },
            "at_risk_by_category": {
                "filter": _available_in("now/d", "now+90d/d"),
                "aggs": {"terms": _value_terms("product_category")},
            },
            "at_risk_by_location": {
                "filter": _available_in("now/d", "now+90d/d"),
                "aggs": {"terms": _value_terms("location_name.keyword")},
            },
        },
    }


def parse_response(response: dict, query: ValueAtRiskQuery) -> ValueAtRiskResult:
    aggs = response.get("aggregations", {})
    buckets = {b["key"]: b for b in aggs.get("buckets", {}).get("buckets", [])}

    def bucket_value(key: str) -> float:
        return float(buckets.get(key, {}).get("value", {}).get("value") or 0.0)

    months = aggs.get("forecast", {}).get("by_month", {}).get("buckets", [])
    raw = [
        (m.get("key_as_string", ""), float(m.get("value", {}).get("value") or 0.0)) for m in months
    ]
    peak = max((v for _, v in raw), default=0.0)
    forecast = [
        ForecastPoint(month=label, value=v, pct=round(v / peak * 100, 1) if peak else 0.0)
        for label, v in raw
    ]

    return ValueAtRiskResult(
        expired_value=bucket_value("expired"),
        expiring_30d_value=bucket_value("30d"),
        expiring_90d_value=bucket_value("90d"),
        forecast=forecast,
        by_category=_buckets(aggs.get("at_risk_by_category", {}).get("terms", {})),
        by_location=_buckets(aggs.get("at_risk_by_location", {}).get("terms", {})),
        engine_took_ms=response.get("took", 0),
    )


def _buckets(agg: dict) -> list[ValueBucket]:
    out = []
    for b in agg.get("buckets", []):
        if not b.get("key"):
            continue
        out.append(
            ValueBucket(
                key=str(b["key"]),
                value=float(b.get("value", {}).get("value") or 0.0),
                quantity=int(b.get("units", {}).get("value") or 0),
                items=int(b.get("doc_count", 0)),
            )
        )
    return out
