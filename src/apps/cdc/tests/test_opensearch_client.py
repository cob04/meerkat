from unittest.mock import MagicMock, patch

import pytest

from apps.cdc.opensearch_client import (
    INVENTORY_INDEX,
    INVENTORY_MAPPING,
    MOVEMENTS_INDEX,
    MOVEMENTS_MAPPING,
    create_index,
    delete_document,
    index_document,
)


@pytest.mark.unit
class TestOpenSearchClient:
    def test_create_index_when_not_exists(self):
        client = MagicMock()
        client.indices.exists.return_value = False

        create_index(client)

        assert client.indices.create.call_count == 2
        client.indices.create.assert_any_call(index=INVENTORY_INDEX, body=INVENTORY_MAPPING)
        client.indices.create.assert_any_call(index=MOVEMENTS_INDEX, body=MOVEMENTS_MAPPING)

    def test_create_index_skips_when_exists(self):
        client = MagicMock()
        client.indices.exists.return_value = True

        create_index(client)

        client.indices.create.assert_not_called()

    def test_create_index_recreate_deletes_first(self):
        client = MagicMock()
        client.indices.exists.return_value = True

        create_index(client, recreate=True)

        assert client.indices.delete.call_count == 2
        client.indices.delete.assert_any_call(index=INVENTORY_INDEX)
        assert client.indices.create.call_count == 2

    def test_index_document(self):
        client = MagicMock()
        doc = {"item_name": "Test"}

        index_document(client, doc_id=1, document=doc)

        client.index.assert_called_once_with(index=INVENTORY_INDEX, id=1, body=doc)

    def test_delete_document(self):
        client = MagicMock()

        delete_document(client, doc_id=1)

        client.delete.assert_called_once_with(index=INVENTORY_INDEX, id=1, ignore=[404])
