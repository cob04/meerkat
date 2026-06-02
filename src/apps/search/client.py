from django.conf import settings
from opensearchpy import OpenSearch
from opensearchpy.exceptions import ConnectionError, ConnectionTimeout, TransportError


class SearchUnavailable(Exception):
    """Raised when the search backend cannot fulfil the request."""


INVENTORY_INDEX = f"{settings.OPENSEARCH_INDEX_PREFIX}_inventory_items"
MOVEMENTS_INDEX = f"{settings.OPENSEARCH_INDEX_PREFIX}_stock_movements"

CLIENT_TIMEOUT_SECONDS = 0.5


def get_client() -> OpenSearch:
    return OpenSearch(
        hosts=[settings.OPENSEARCH_URL],
        use_ssl=False,
        verify_certs=False,
        timeout=CLIENT_TIMEOUT_SECONDS,
    )


def search(body: dict, index: str = INVENTORY_INDEX) -> dict:
    client = get_client()
    try:
        return client.search(index=index, body=body)
    except (ConnectionError, ConnectionTimeout, TransportError) as exc:
        raise SearchUnavailable(str(exc)) from exc
