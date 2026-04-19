from unittest.mock import patch

import pytest

from apps.search import services
from apps.search.contracts import InventoryQuery


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
