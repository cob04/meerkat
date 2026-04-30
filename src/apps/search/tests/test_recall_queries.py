import pytest

from apps.search.contracts import RecallQuery
from apps.search.queries import recall


@pytest.mark.unit
class TestHasCriteria:
    def test_empty_query_has_no_criteria(self):
        assert RecallQuery().has_criteria is False

    def test_any_field_makes_it_actionable(self):
        assert RecallQuery(manufacturer="Pfizer").has_criteria is True
        assert RecallQuery(batch_pattern="B5*").has_criteria is True
        assert RecallQuery(drug_id=42).has_criteria is True
        assert RecallQuery(created_from="2026-01-01").has_criteria is True
        assert RecallQuery(created_to="2026-04-30").has_criteria is True


@pytest.mark.unit
class TestBuildBody:
    def test_match_all_when_no_criteria(self):
        body = recall.build_body(RecallQuery())

        assert body["query"] == {"match_all": {}}

    def test_manufacturer_uses_match_phrase(self):
        body = recall.build_body(RecallQuery(manufacturer="Pfizer"))

        must = body["query"]["bool"]["must"]
        assert {"match_phrase": {"drug_manufacturer": "Pfizer"}} in must

    def test_batch_pattern_wraps_with_wildcards_when_plain(self):
        body = recall.build_body(RecallQuery(batch_pattern="B500"))

        must = body["query"]["bool"]["must"]
        assert {"wildcard": {"batch_number": "*B500*"}} in must

    def test_batch_pattern_kept_as_is_when_user_supplies_glob(self):
        body = recall.build_body(RecallQuery(batch_pattern="B5*"))

        must = body["query"]["bool"]["must"]
        assert {"wildcard": {"batch_number": "B5*"}} in must

    def test_drug_id_term(self):
        body = recall.build_body(RecallQuery(drug_id=7))

        must = body["query"]["bool"]["must"]
        assert {"term": {"drug_id": 7}} in must

    def test_date_range_uses_gte_lte(self):
        body = recall.build_body(RecallQuery(created_from="2026-01-01", created_to="2026-04-30"))

        must = body["query"]["bool"]["must"]
        assert {"range": {"created_at": {"gte": "2026-01-01", "lte": "2026-04-30"}}} in must

    def test_open_ended_date_range(self):
        body = recall.build_body(RecallQuery(created_from="2026-01-01"))

        must = body["query"]["bool"]["must"]
        assert {"range": {"created_at": {"gte": "2026-01-01"}}} in must

    def test_aggs_include_per_location_quantity_sum(self):
        body = recall.build_body(RecallQuery(manufacturer="GSK"))

        loc = body["aggs"]["by_location"]
        assert loc["terms"]["field"] == "location_name.keyword"
        assert "total_quantity" in loc["aggs"]
        assert body["aggs"]["network_quantity"] == {"sum": {"field": "quantity"}}


@pytest.mark.unit
class TestParseResponse:
    def test_extracts_matches_and_buckets(self):
        response = {
            "took": 7,
            "hits": {
                "total": {"value": 2},
                "hits": [
                    {
                        "_id": "10",
                        "_source": {
                            "item_name": "Lantus 100IU 30d-010",
                            "product_name": "Lantus",
                            "drug_inn_name": "Insulin glargine",
                            "drug_manufacturer": "Sanofi",
                            "batch_number": "B5421-010",
                            "location_name": "Karen Pharmacy",
                            "quantity": 12,
                            "status": "available",
                            "expiry_date": "2026-12-01",
                        },
                    }
                ],
            },
            "aggregations": {
                "by_location": {
                    "buckets": [
                        {
                            "key": "Karen Pharmacy",
                            "doc_count": 1,
                            "total_quantity": {"value": 12.0},
                        }
                    ]
                },
                "network_quantity": {"value": 12.0},
            },
        }

        impact = recall.parse_response(response)

        assert impact.total_items == 2
        assert impact.total_quantity == 12
        assert impact.engine_took_ms == 7
        assert len(impact.matches) == 1
        match = impact.matches[0]
        assert match.id == 10
        assert match.manufacturer == "Sanofi"
        assert match.drug_inn_name == "Insulin glargine"
        assert match.location_name == "Karen Pharmacy"
        assert match.quantity == 12
        assert match.status == "available"
        assert impact.by_location[0].location_name == "Karen Pharmacy"
        assert impact.by_location[0].quantity == 12
        assert impact.by_location[0].item_count == 1

    def test_skips_blank_location_buckets(self):
        response = {
            "took": 1,
            "hits": {"total": {"value": 0}, "hits": []},
            "aggregations": {
                "by_location": {
                    "buckets": [{"key": "", "doc_count": 1, "total_quantity": {"value": 1}}]
                },
                "network_quantity": {"value": 0},
            },
        }

        impact = recall.parse_response(response)

        assert impact.by_location == []
