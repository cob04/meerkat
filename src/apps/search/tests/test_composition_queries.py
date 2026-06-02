import pytest

from apps.search.contracts import CompositionQuery
from apps.search.queries import composition


@pytest.mark.unit
def test_build_body_aggregates_dimensions():
    body = composition.build_body(CompositionQuery())
    aggs = body["aggs"]
    assert aggs["by_manufacturer"]["terms"]["field"] == "drug_manufacturer.keyword"
    assert aggs["by_atc_class"]["terms"]["field"] == "drug_atc_class"
    assert aggs["by_prescription"]["terms"]["field"] == "drug_requires_prescription"
    assert aggs["by_manufacturer"]["aggs"]["value"]["sum"]["field"] == "line_value"


@pytest.mark.unit
def test_parse_response_labels_and_concentration():
    response = {
        "took": 5,
        "aggregations": {
            "total_value": {"value": 1000.0},
            "by_manufacturer": {
                "buckets": [
                    {
                        "key": "GSK",
                        "doc_count": 5,
                        "value": {"value": 400.0},
                        "units": {"value": 100.0},
                    },
                    {
                        "key": "Pfizer",
                        "doc_count": 3,
                        "value": {"value": 200.0},
                        "units": {"value": 60.0},
                    },
                ]
            },
            "by_atc_class": {
                "buckets": [
                    {
                        "key": "C",
                        "doc_count": 2,
                        "value": {"value": 300.0},
                        "units": {"value": 50.0},
                    }
                ]
            },
            "by_dosage_form": {
                "buckets": [
                    {
                        "key": "tablet",
                        "doc_count": 4,
                        "value": {"value": 500.0},
                        "units": {"value": 90.0},
                    }
                ]
            },
            "by_prescription": {
                "buckets": [
                    {
                        "key": 1,
                        "key_as_string": "true",
                        "doc_count": 6,
                        "value": {"value": 700.0},
                        "units": {"value": 120.0},
                    },
                    {
                        "key": 0,
                        "key_as_string": "false",
                        "doc_count": 2,
                        "value": {"value": 300.0},
                        "units": {"value": 40.0},
                    },
                ]
            },
        },
    }
    result = composition.parse_response(response, CompositionQuery())
    assert result.total_value == 1000.0
    assert result.top_manufacturer == "GSK"
    assert result.supplier_concentration == 40.0  # 400 / 1000
    assert result.by_atc_class[0].key == "Cardiovascular system"
    assert result.by_dosage_form[0].key == "Tablet"
    pres = {b.key for b in result.by_prescription}
    assert pres == {"Prescription required", "Over the counter"}
