from unittest.mock import patch

import pytest
from opensearchpy.exceptions import ConnectionError, ConnectionTimeout, TransportError

from apps.search import client


@pytest.mark.unit
class TestSearchClient:
    def test_returns_response_on_success(self):
        with patch("apps.search.client.get_client") as get_client:
            get_client.return_value.search.return_value = {"hits": {"hits": []}}

            response = client.search({"query": {"match_all": {}}})

        assert response == {"hits": {"hits": []}}

    def test_raises_search_unavailable_on_connection_error(self):
        with patch("apps.search.client.get_client") as get_client:
            get_client.return_value.search.side_effect = ConnectionError(
                "N/A", "connection refused", Exception()
            )

            with pytest.raises(client.SearchUnavailable):
                client.search({})

    def test_raises_search_unavailable_on_timeout(self):
        with patch("apps.search.client.get_client") as get_client:
            get_client.return_value.search.side_effect = ConnectionTimeout(
                "N/A", "request timed out", Exception()
            )

            with pytest.raises(client.SearchUnavailable):
                client.search({})

    def test_raises_search_unavailable_on_transport_error(self):
        with patch("apps.search.client.get_client") as get_client:
            get_client.return_value.search.side_effect = TransportError(500, "nope", {})

            with pytest.raises(client.SearchUnavailable):
                client.search({})
