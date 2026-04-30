import pytest

from apps.search.contracts import InventoryQuery
from apps.search.queries import search


@pytest.mark.unit
class TestBuildBody:
    def test_multi_match_when_query_provided(self):
        body = search.build_body(InventoryQuery(q="paracetamol", page=1, page_size=10))

        assert body["from"] == 0
        assert body["size"] == 10
        assert "multi_match" in body["query"]
        assert body["query"]["multi_match"]["fuzziness"] == "AUTO"
        assert "product_name^3" in body["query"]["multi_match"]["fields"]

    def test_match_all_when_query_blank(self):
        body = search.build_body(InventoryQuery(q=None))

        assert "match_all" in body["query"]

    def test_pagination_offset(self):
        body = search.build_body(InventoryQuery(q="x", page=3, page_size=20))

        assert body["from"] == 40
        assert body["size"] == 20

    def test_minimum_page_is_one(self):
        body = search.build_body(InventoryQuery(q="x", page=0, page_size=10))

        assert body["from"] == 0

    def test_default_sort_includes_score_and_updated_at(self):
        body = search.build_body(InventoryQuery(q="x", sort="_score"))

        assert body["sort"][0] == "_score"
        assert body["sort"][1] == {"updated_at": {"order": "desc"}}

    def test_custom_descending_sort(self):
        body = search.build_body(InventoryQuery(q="x", sort="-expiry_date"))

        assert body["sort"] == [{"expiry_date": {"order": "desc"}}]

    def test_custom_ascending_sort(self):
        body = search.build_body(InventoryQuery(q="x", sort="expiry_date"))

        assert body["sort"] == [{"expiry_date": {"order": "asc"}}]


@pytest.mark.unit
class TestFacetAggs:
    def test_body_includes_status_location_category_aggs(self):
        body = search.build_body(InventoryQuery(q="panadol"))

        assert set(body["aggs"].keys()) == {"status", "location", "category"}
        for facet, field_name in search.FACET_FIELDS.items():
            agg = body["aggs"][facet]
            assert agg["aggs"]["buckets"]["terms"]["field"] == field_name

    def test_no_post_filter_without_selections(self):
        body = search.build_body(InventoryQuery(q="x"))

        assert "post_filter" not in body

    def test_post_filter_combines_all_selections(self):
        body = search.build_body(
            InventoryQuery(
                q="x",
                status=["available", "reserved"],
                location=["Main Pharmacy"],
                category=["antibiotic"],
            )
        )

        clauses = body["post_filter"]["bool"]["filter"]
        assert {"terms": {"status": ["available", "reserved"]}} in clauses
        assert {"terms": {"location_name.keyword": ["Main Pharmacy"]}} in clauses
        assert {"terms": {"product_category": ["antibiotic"]}} in clauses

    def test_facet_agg_excludes_its_own_filter(self):
        body = search.build_body(
            InventoryQuery(q="x", status=["available"], category=["antibiotic"])
        )

        status_filters = body["aggs"]["status"]["filter"]["bool"]["filter"]
        assert {"terms": {"status": ["available"]}} not in status_filters
        assert {"terms": {"product_category": ["antibiotic"]}} in status_filters

        category_filters = body["aggs"]["category"]["filter"]["bool"]["filter"]
        assert {"terms": {"status": ["available"]}} in category_filters
        assert {"terms": {"product_category": ["antibiotic"]}} not in category_filters


@pytest.mark.unit
class TestExpiryBucketFilter:
    def test_no_bucket_keeps_query_flat(self):
        body = search.build_body(InventoryQuery(q="x"))

        assert "bool" not in body["query"]

    def test_bucket_wraps_query_with_range_filter(self):
        body = search.build_body(InventoryQuery(q="x", expiry_bucket="30d"))

        assert "bool" in body["query"]
        filters = body["query"]["bool"]["filter"]
        assert filters == [{"range": {"expiry_date": {"gte": "now/d", "lt": "now+30d/d"}}}]

    def test_unknown_bucket_ignored(self):
        body = search.build_body(InventoryQuery(q="x", expiry_bucket="bogus"))

        assert "bool" not in body["query"]

    def test_expired_bucket_uses_lt_today(self):
        body = search.build_body(InventoryQuery(q="x", expiry_bucket="expired"))

        assert body["query"]["bool"]["filter"] == [{"range": {"expiry_date": {"lt": "now/d"}}}]


@pytest.mark.unit
class TestParseResponse:
    def test_parses_hits_into_docs(self):
        response = {
            "took": 12,
            "hits": {
                "total": {"value": 2},
                "hits": [
                    {
                        "_id": "1",
                        "_score": 1.4,
                        "_source": {
                            "item_name": "Paracetamol 500mg",
                            "product_name": "Panadol",
                            "batch_number": "B001",
                            "location_name": "Main Pharmacy",
                            "quantity": 100,
                            "status": "available",
                            "expiry_date": "2027-01-01",
                        },
                    },
                    {
                        "_id": "2",
                        "_score": 0.9,
                        "_source": {
                            "item_name": "Paracetamol 250mg",
                            "batch_number": "B002",
                            "quantity": 0,
                            "status": "expired",
                        },
                    },
                ],
            },
        }

        results = search.parse_response(
            response, InventoryQuery(q="paracetamol", page=1, page_size=25)
        )

        assert results.total == 2
        assert results.engine_took_ms == 12
        assert len(results.items) == 2
        assert results.items[0].id == 1
        assert results.items[0].item_name == "Paracetamol 500mg"
        assert results.items[0].score == 1.4
        assert results.items[1].product_name is None

    def test_empty_response(self):
        response = {"took": 3, "hits": {"total": {"value": 0}, "hits": []}}

        results = search.parse_response(response, InventoryQuery(q="xyz"))

        assert results.total == 0
        assert results.items == []
        assert results.engine_took_ms == 3

    def test_extracts_facet_buckets(self):
        response = {
            "took": 5,
            "hits": {"total": {"value": 0}, "hits": []},
            "aggregations": {
                "status": {
                    "buckets": {
                        "buckets": [
                            {"key": "available", "doc_count": 12},
                            {"key": "expired", "doc_count": 3},
                        ]
                    }
                },
                "location": {"buckets": {"buckets": [{"key": "Main Pharmacy", "doc_count": 10}]}},
                "category": {"buckets": {"buckets": [{"key": "antibiotic", "doc_count": 7}]}},
            },
        }

        results = search.parse_response(response, InventoryQuery(q="x"))

        assert results.facets.status == {"available": 12, "expired": 3}
        assert results.facets.location == {"Main Pharmacy": 10}
        assert results.facets.category == {"antibiotic": 7}

    def test_missing_aggs_yields_empty_facets(self):
        response = {"took": 1, "hits": {"total": {"value": 0}, "hits": []}}

        results = search.parse_response(response, InventoryQuery(q="x"))

        assert results.facets.status == {}
        assert results.facets.location == {}
        assert results.facets.category == {}
