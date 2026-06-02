import logging

from django.conf import settings
from opensearchpy import OpenSearch

logger = logging.getLogger(__name__)

INVENTORY_INDEX = f"{settings.OPENSEARCH_INDEX_PREFIX}_inventory_items"
MOVEMENTS_INDEX = f"{settings.OPENSEARCH_INDEX_PREFIX}_stock_movements"

MOVEMENTS_MAPPING = {
    "mappings": {
        "properties": {
            "movement_type": {"type": "keyword"},
            "quantity": {"type": "integer"},
            "item_name": {"type": "text", "fields": {"keyword": {"type": "keyword"}}},
            "product_name": {"type": "text", "fields": {"keyword": {"type": "keyword"}}},
            "product_category": {"type": "keyword"},
            "location_name": {"type": "text", "fields": {"keyword": {"type": "keyword"}}},
            "performed_by": {"type": "keyword"},
            "created_at": {"type": "date"},
        }
    }
}

INVENTORY_MAPPING = {
    "mappings": {
        "properties": {
            "item_name": {"type": "text", "fields": {"keyword": {"type": "keyword"}}},
            "product_name": {"type": "text", "fields": {"keyword": {"type": "keyword"}}},
            "product_sku": {"type": "keyword"},
            "product_category": {"type": "keyword"},
            "is_drug": {"type": "boolean"},
            "drug_inn_name": {"type": "text", "fields": {"keyword": {"type": "keyword"}}},
            "drug_brand_name": {"type": "text", "fields": {"keyword": {"type": "keyword"}}},
            "drug_atc_code": {"type": "keyword"},
            "drug_atc_class": {"type": "keyword"},
            "drug_dosage_form": {"type": "keyword"},
            "drug_strength": {"type": "keyword"},
            "drug_manufacturer": {"type": "text", "fields": {"keyword": {"type": "keyword"}}},
            "drug_requires_prescription": {"type": "boolean"},
            "drug_storage_condition": {"type": "keyword"},
            "product_id": {"type": "long"},
            "drug_id": {"type": "long"},
            "location_id": {"type": "long"},
            "location_name": {"type": "text", "fields": {"keyword": {"type": "keyword"}}},
            "location_type": {"type": "keyword"},
            "location_geo": {"type": "geo_point"},
            "batch_number": {"type": "keyword"},
            "quantity": {"type": "integer"},
            "expiry_date": {"type": "date"},
            "unit_cost": {"type": "scaled_float", "scaling_factor": 100},
            "line_value": {"type": "scaled_float", "scaling_factor": 100},
            "status": {"type": "keyword"},
            "created_at": {"type": "date"},
            "updated_at": {"type": "date"},
        }
    }
}


def get_client() -> OpenSearch:
    return OpenSearch(
        hosts=[settings.OPENSEARCH_URL],
        use_ssl=False,
        verify_certs=False,
    )


def _create(client: OpenSearch, index: str, mapping: dict, recreate: bool):
    if client.indices.exists(index=index):
        if recreate:
            client.indices.delete(index=index)
            logger.info("Deleted index %s", index)
        else:
            logger.info("Index %s already exists", index)
            return
    client.indices.create(index=index, body=mapping)
    logger.info("Created index %s", index)


def create_index(client: OpenSearch, recreate: bool = False):
    _create(client, INVENTORY_INDEX, INVENTORY_MAPPING, recreate)
    _create(client, MOVEMENTS_INDEX, MOVEMENTS_MAPPING, recreate)


def index_document(client: OpenSearch, doc_id: int, document: dict, index: str = INVENTORY_INDEX):
    client.index(index=index, id=doc_id, body=document)


def delete_document(client: OpenSearch, doc_id: int, index: str = INVENTORY_INDEX):
    client.delete(index=index, id=doc_id, ignore=[404])
