from unittest.mock import patch

import pytest

from apps.search import client, services
from apps.search.contracts import InventoryDoc, InventoryQuery, InventoryResults


@pytest.mark.unit
class TestSearchInventory:
    def test_calls_client_with_built_body_and_parses_response(self):
        fake_response = {
            "took": 5,
            "hits": {
                "total": {"value": 1},
                "hits": [
                    {
                        "_id": "42",
                        "_score": 2.1,
                        "_source": {
                            "item_name": "Ibuprofen 400mg",
                            "batch_number": "B100",
                            "quantity": 50,
                            "status": "available",
                        },
                    }
                ],
            },
        }

        with patch("apps.search.services.client.search", return_value=fake_response) as mock_search:
            results = services.search_inventory(InventoryQuery(q="ibuprofen", page=1, page_size=10))

        assert mock_search.call_count == 1
        body = mock_search.call_args.args[0]
        assert "multi_match" in body["query"]
        assert body["size"] == 10
        assert results.total == 1
        assert results.items[0].id == 42
        assert results.engine_took_ms == 5


def _doc(item_name, product_name):
    return InventoryDoc(
        id=1,
        item_name=item_name,
        product_name=product_name,
        batch_number="B",
        location_name="L",
        quantity=1,
        status="available",
        expiry_date=None,
    )


@pytest.mark.unit
class TestSuggest:
    def test_dedupes_product_and_item_names(self):
        results = InventoryResults(
            items=[_doc("Panadol 500", "Panadol"), _doc("Panadol 250", "Panadol")],
            total=2,
            page=1,
            page_size=16,
            engine_took_ms=1,
            facets=None,
        )
        with patch("apps.search.services.search_inventory", return_value=results):
            assert services.suggest("pan") == ["Panadol", "Panadol 500", "Panadol 250"]

    def test_blank_query_skips_search(self):
        with patch("apps.search.services.search_inventory") as mock:
            assert services.suggest("  ") == []
        assert mock.call_count == 0

    def test_unavailable_returns_empty(self):
        with patch(
            "apps.search.services.search_inventory",
            side_effect=client.SearchUnavailable("down"),
        ):
            assert services.suggest("pan") == []


@pytest.mark.unit
class TestInventoryValue:
    def test_builds_body_and_parses(self):
        from apps.search.contracts import ValueQuery

        fake_response = {
            "took": 2,
            "hits": {"total": {"value": 3}},
            "aggregations": {
                "total_value": {"value": 999.0},
                "total_quantity": {"value": 30.0},
                "by_location": {"buckets": []},
                "by_category": {"buckets": []},
                "by_manufacturer": {"buckets": []},
            },
        }
        with patch("apps.search.services.client.search", return_value=fake_response) as mock_search:
            result = services.inventory_value(ValueQuery())

        body = mock_search.call_args.args[0]
        assert body["aggs"]["total_value"]["sum"]["field"] == "line_value"
        assert result.total_value == 999.0
        assert result.total_items == 3
