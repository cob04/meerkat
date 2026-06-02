import pytest

from apps.search.contracts import CoverageQuery
from apps.search.queries import coverage


@pytest.mark.unit
def test_build_body_filters_available_and_buckets_products():
    body = coverage.build_body(CoverageQuery())
    assert {"term": {"status": "available"}} in body["query"]["bool"]["filter"]
    products = body["aggs"]["products"]
    assert products["terms"]["field"] == "product_name.keyword"
    assert products["aggs"]["site_count"]["cardinality"]["field"] == "location_id"


@pytest.mark.unit
def test_parse_response_bands_and_single_source():
    response = {
        "took": 6,
        "aggregations": {
            "products": {
                "buckets": [
                    {
                        "key": "Lantus",
                        "site_count": {"value": 1},
                        "units": {"value": 40.0},
                        "value": {"value": 800.0},
                        "top_site": {"buckets": [{"key": "Karen Pharmacy"}]},
                    },
                    {
                        "key": "Panadol",
                        "site_count": {"value": 2},
                        "units": {"value": 100.0},
                        "value": {"value": 200.0},
                        "top_site": {"buckets": [{"key": "Westlands"}]},
                    },
                    {
                        "key": "Amoxil",
                        "site_count": {"value": 5},
                        "units": {"value": 300.0},
                        "value": {"value": 500.0},
                        "top_site": {"buckets": [{"key": "Depot"}]},
                    },
                ]
            }
        },
    }
    result = coverage.parse_response(response, CoverageQuery())
    assert result.products_in_stock == 3
    assert result.single_source_count == 1
    assert result.well_covered_count == 1
    bands = {b.label: b.products for b in result.coverage_bands}
    assert bands == {"1 site": 1, "2 sites": 1, "3+ sites": 1}
    assert result.single_source[0].product == "Lantus"
    assert result.single_source[0].site == "Karen Pharmacy"
    assert result.single_source[0].value == 800.0
