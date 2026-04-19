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
