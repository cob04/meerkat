import pytest

from apps.search.contracts import StockQuery
from apps.search.queries import stock


@pytest.mark.unit
class TestBuildBody:
    def test_filters_to_available_under_threshold(self):
        body = stock.build_body(StockQuery(threshold=10))

        filters = body["query"]["bool"]["filter"]
        assert {"term": {"status": "available"}} in filters
        assert {"range": {"quantity": {"lt": 10}}} in filters

    def test_threshold_passed_through(self):
        body = stock.build_body(StockQuery(threshold=5))

        assert {"range": {"quantity": {"lt": 5}}} in body["query"]["bool"]["filter"]

    def test_location_filter_added_when_provided(self):
        body = stock.build_body(StockQuery(location=["Westlands"]))

        filters = body["query"]["bool"]["filter"]
        assert {"terms": {"location_name.keyword": ["Westlands"]}} in filters

    def test_category_filter_added_when_provided(self):
        body = stock.build_body(StockQuery(category=["antibiotic"]))

        filters = body["query"]["bool"]["filter"]
        assert {"terms": {"product_category": ["antibiotic"]}} in filters

    def test_sorts_by_quantity_then_expiry(self):
        body = stock.build_body(StockQuery())

        assert body["sort"][0] == {"quantity": {"order": "asc"}}
        assert body["sort"][1] == {"expiry_date": {"order": "asc"}}

    def test_aggregations_present(self):
        body = stock.build_body(StockQuery())

        assert "out_of_stock" in body["aggs"]
        assert body["aggs"]["out_of_stock"]["filter"] == {"term": {"quantity": 0}}
        assert body["aggs"]["by_location"]["terms"]["field"] == "location_name.keyword"
        assert body["aggs"]["by_category"]["terms"]["field"] == "product_category"


@pytest.mark.unit
class TestParseResponse:
    def test_extracts_total_and_out_of_stock(self):
        response = {
            "took": 4,
            "hits": {"total": {"value": 8}, "hits": []},
            "aggregations": {
                "out_of_stock": {"doc_count": 3},
                "by_location": {"buckets": []},
                "by_category": {"buckets": []},
            },
        }

        result = stock.parse_response(response, StockQuery(threshold=10))

        assert result.threshold == 10
        assert result.total_items == 8
        assert result.out_of_stock == 3
        assert result.engine_took_ms == 4
        assert result.items == []

    def test_extracts_items_with_quantity_and_metadata(self):
        response = {
            "took": 1,
            "hits": {
                "total": {"value": 1},
                "hits": [
                    {
                        "_id": "42",
                        "_source": {
                            "item_name": "Amoxil 500 - low",
                            "product_name": "Amoxil",
                            "location_name": "Karen",
                            "product_category": "antibiotic",
                            "quantity": 2,
                            "expiry_date": "2026-09-12",
                        },
                    }
                ],
            },
            "aggregations": {
                "out_of_stock": {"doc_count": 0},
                "by_location": {"buckets": [{"key": "Karen", "doc_count": 1}]},
                "by_category": {"buckets": [{"key": "antibiotic", "doc_count": 1}]},
            },
        }

        result = stock.parse_response(response, StockQuery())

        assert len(result.items) == 1
        assert result.items[0].id == 42
        assert result.items[0].item_name == "Amoxil 500 - low"
        assert result.items[0].location_name == "Karen"
        assert result.items[0].category == "antibiotic"
        assert result.items[0].quantity == 2
        assert result.by_location[0].key == "Karen"
        assert result.by_category[0].key == "antibiotic"

    def test_skips_blank_bucket_keys(self):
        response = {
            "took": 1,
            "hits": {"total": {"value": 0}, "hits": []},
            "aggregations": {
                "out_of_stock": {"doc_count": 0},
                "by_location": {"buckets": [{"key": "", "doc_count": 1}]},
                "by_category": {"buckets": [{"key": "", "doc_count": 1}]},
            },
        }

        result = stock.parse_response(response, StockQuery())

        assert result.by_location == []
        assert result.by_category == []
