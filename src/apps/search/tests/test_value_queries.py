import pytest

from apps.search.contracts import ValueQuery
from apps.search.queries import value


@pytest.mark.unit
def test_build_body_aggregates_value():
    body = value.build_body(ValueQuery())
    assert body["size"] == 0
    aggs = body["aggs"]
    assert aggs["total_value"]["sum"]["field"] == "line_value"
    assert aggs["by_location"]["aggs"]["value"]["sum"]["field"] == "line_value"
    assert aggs["by_manufacturer"]["terms"]["field"] == "drug_manufacturer.keyword"


@pytest.mark.unit
def test_build_body_applies_filters():
    body = value.build_body(ValueQuery(location=["Karen"], category=["antibiotic"]))
    filters = body["query"]["bool"]["filter"]
    assert {"terms": {"location_name.keyword": ["Karen"]}} in filters
    assert {"terms": {"product_category": ["antibiotic"]}} in filters


@pytest.mark.unit
def test_parse_response_builds_result():
    response = {
        "took": 3,
        "hits": {"total": {"value": 5}},
        "aggregations": {
            "total_value": {"value": 1000.0},
            "total_quantity": {"value": 200.0},
            "by_location": {
                "buckets": [
                    {
                        "key": "Karen",
                        "doc_count": 2,
                        "value": {"value": 600.0},
                        "units": {"value": 120.0},
                    }
                ]
            },
            "by_category": {"buckets": []},
            "by_manufacturer": {"buckets": []},
        },
    }
    result = value.parse_response(response, ValueQuery())
    assert result.total_value == 1000.0
    assert result.total_quantity == 200
    assert result.total_items == 5
    assert result.by_location[0].key == "Karen"
    assert result.by_location[0].value == 600.0
    assert result.by_location[0].quantity == 120
    assert result.by_location[0].items == 2
