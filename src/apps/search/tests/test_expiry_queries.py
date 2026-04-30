import pytest

from apps.search.contracts import ExpiryQuery
from apps.search.queries import expiry


@pytest.mark.unit
class TestBuildBody:
    def test_size_zero_no_hits(self):
        body = expiry.build_body(ExpiryQuery())

        assert body["size"] == 0

    def test_must_exists_expiry_date(self):
        body = expiry.build_body(ExpiryQuery())

        assert {"exists": {"field": "expiry_date"}} in body["query"]["bool"]["must"]

    def test_no_filters_when_query_empty(self):
        body = expiry.build_body(ExpiryQuery())

        assert body["query"]["bool"]["filter"] == []

    def test_location_filter_passed_through(self):
        body = expiry.build_body(ExpiryQuery(location=["Westlands", "Karen"]))

        filters = body["query"]["bool"]["filter"]
        assert {"terms": {"location_name.keyword": ["Westlands", "Karen"]}} in filters

    def test_category_filter_passed_through(self):
        body = expiry.build_body(ExpiryQuery(category=["antibiotic"]))

        filters = body["query"]["bool"]["filter"]
        assert {"terms": {"product_category": ["antibiotic"]}} in filters

    def test_top_level_date_range_buckets(self):
        body = expiry.build_body(ExpiryQuery())

        ranges = body["aggs"]["by_bucket"]["date_range"]["ranges"]
        keys = [r["key"] for r in ranges]
        assert keys == ["expired", "30d", "90d", "90plus"]
        assert body["aggs"]["by_bucket"]["date_range"]["field"] == "expiry_date"

    def test_per_location_terms_with_nested_buckets(self):
        body = expiry.build_body(ExpiryQuery())

        loc = body["aggs"]["by_location"]
        assert loc["terms"]["field"] == "location_name.keyword"
        assert "by_bucket" in loc["aggs"]
        assert loc["aggs"]["by_bucket"]["date_range"]["field"] == "expiry_date"

    def test_per_category_terms_with_nested_buckets(self):
        body = expiry.build_body(ExpiryQuery())

        cat = body["aggs"]["by_category"]
        assert cat["terms"]["field"] == "product_category"
        assert "by_bucket" in cat["aggs"]


@pytest.mark.unit
class TestParseResponse:
    def test_extracts_top_level_buckets_in_canonical_order(self):
        response = {
            "took": 5,
            "hits": {"total": {"value": 12}},
            "aggregations": {
                "by_bucket": {
                    "buckets": [
                        {"key": "expired", "doc_count": 2},
                        {"key": "30d", "doc_count": 4},
                        {"key": "90d", "doc_count": 3},
                        {"key": "90plus", "doc_count": 3},
                    ]
                },
                "by_location": {"buckets": []},
                "by_category": {"buckets": []},
            },
        }

        rollup = expiry.parse_response(response)

        assert rollup.total_items == 12
        assert rollup.engine_took_ms == 5
        assert [b.key for b in rollup.buckets] == ["expired", "30d", "90d", "90plus"]
        assert rollup.buckets[0].count == 2
        assert rollup.buckets[0].label == "Expired"

    def test_fills_zero_for_missing_keys(self):
        response = {
            "took": 1,
            "hits": {"total": {"value": 2}},
            "aggregations": {
                "by_bucket": {"buckets": [{"key": "expired", "doc_count": 2}]},
                "by_location": {"buckets": []},
                "by_category": {"buckets": []},
            },
        }

        rollup = expiry.parse_response(response)

        counts = {b.key: b.count for b in rollup.buckets}
        assert counts == {"expired": 2, "30d": 0, "90d": 0, "90plus": 0}

    def test_extracts_per_location(self):
        response = {
            "took": 1,
            "hits": {"total": {"value": 3}},
            "aggregations": {
                "by_bucket": {"buckets": []},
                "by_location": {
                    "buckets": [
                        {
                            "key": "Westlands",
                            "doc_count": 3,
                            "by_bucket": {
                                "buckets": [
                                    {"key": "expired", "doc_count": 1},
                                    {"key": "30d", "doc_count": 2},
                                    {"key": "90d", "doc_count": 0},
                                    {"key": "90plus", "doc_count": 0},
                                ]
                            },
                        }
                    ]
                },
                "by_category": {"buckets": []},
            },
        }

        rollup = expiry.parse_response(response)

        assert len(rollup.by_location) == 1
        assert rollup.by_location[0].location_name == "Westlands"
        assert rollup.by_location[0].total == 3
        assert rollup.by_location[0].buckets[0].key == "expired"
        assert rollup.by_location[0].buckets[0].count == 1
        assert rollup.by_location[0].buckets[1].count == 2

    def test_skips_blank_category_keys(self):
        response = {
            "took": 1,
            "hits": {"total": {"value": 1}},
            "aggregations": {
                "by_bucket": {"buckets": []},
                "by_location": {"buckets": []},
                "by_category": {
                    "buckets": [
                        {
                            "key": "",
                            "doc_count": 1,
                            "by_bucket": {"buckets": []},
                        },
                        {
                            "key": "antibiotic",
                            "doc_count": 1,
                            "by_bucket": {"buckets": []},
                        },
                    ]
                },
            },
        }

        rollup = expiry.parse_response(response)

        assert [c.category for c in rollup.by_category] == ["antibiotic"]
