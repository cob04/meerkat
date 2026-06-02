import pytest

from apps.search.contracts import ValueAtRiskQuery
from apps.search.queries import value_at_risk


@pytest.mark.unit
def test_build_body_has_buckets_forecast_and_breakdowns():
    body = value_at_risk.build_body(ValueAtRiskQuery(forecast_months=6))
    aggs = body["aggs"]
    assert aggs["buckets"]["date_range"]["field"] == "expiry_date"
    assert aggs["forecast"]["aggs"]["by_month"]["date_histogram"]["calendar_interval"] == "month"
    assert aggs["at_risk_by_category"]["aggs"]["terms"]["terms"]["field"] == "product_category"
    # forecast/breakdowns scoped to available, future-expiring stock
    filt = aggs["forecast"]["filter"]["bool"]["filter"]
    assert {"term": {"status": "available"}} in filt


@pytest.mark.unit
def test_parse_response_builds_result():
    response = {
        "took": 4,
        "aggregations": {
            "buckets": {
                "buckets": [
                    {"key": "expired", "value": {"value": 500.0}},
                    {"key": "30d", "value": {"value": 200.0}},
                    {"key": "90d", "value": {"value": 800.0}},
                ]
            },
            "forecast": {
                "by_month": {
                    "buckets": [
                        {"key_as_string": "2026-06", "value": {"value": 100.0}},
                        {"key_as_string": "2026-07", "value": {"value": 50.0}},
                    ]
                }
            },
            "at_risk_by_category": {
                "terms": {
                    "buckets": [
                        {
                            "key": "antibiotic",
                            "doc_count": 3,
                            "value": {"value": 300.0},
                            "units": {"value": 40.0},
                        }
                    ]
                }
            },
            "at_risk_by_location": {"terms": {"buckets": []}},
        },
    }
    result = value_at_risk.parse_response(response, ValueAtRiskQuery())
    assert result.expired_value == 500.0
    assert result.expiring_30d_value == 200.0
    assert result.expiring_90d_value == 800.0
    assert result.forecast[0].month == "2026-06"
    assert result.forecast[0].pct == 100.0  # peak month
    assert result.forecast[1].pct == 50.0
    assert result.by_category[0].key == "antibiotic"
    assert result.by_category[0].value == 300.0
