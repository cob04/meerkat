from decimal import Decimal

import pytest

from apps.catalog.models import Drug, InventoryItem, Location, Product
from apps.cdc.transformers import (
    TOPIC_DRUG,
    TOPIC_INVENTORY,
    TOPIC_LOCATION,
    TOPIC_PRODUCT,
    DeleteAction,
    IndexAction,
    transform,
)


@pytest.fixture
def location(db):
    return Location.objects.create(name="Warehouse A", location_type="warehouse")


@pytest.fixture
def product(db):
    return Product.objects.create(name="Aspirin", sku="ASP-100", unit_price=Decimal("5.00"))


@pytest.fixture
def drug(product):
    return Drug.objects.create(
        product=product,
        inn_name="Acetylsalicylic acid",
        atc_code="N02BA01",
        dosage_form="tablet",
        strength="100",
        unit="mg",
    )


@pytest.fixture
def item(location, product):
    return InventoryItem.objects.create(
        item_name="Aspirin 100mg",
        product=product,
        location=location,
        batch_number="BATCH-001",
        quantity=50,
        expiry_date="2027-06-01",
        unit_cost=Decimal("5.00"),
    )


@pytest.mark.unit
class TestInventoryItemTransform:
    def test_create_produces_index_action(self, item):
        event = {"op": "c", "after": {"id": item.pk, "deleted_at": None}, "before": None}
        actions = transform(TOPIC_INVENTORY, event)

        assert len(actions) == 1
        assert isinstance(actions[0], IndexAction)
        assert actions[0].doc_id == item.pk
        assert actions[0].document["item_name"] == "Aspirin 100mg"
        assert actions[0].document["batch_number"] == "BATCH-001"

    def test_snapshot_read_produces_index_action(self, item):
        event = {"op": "r", "after": {"id": item.pk, "deleted_at": None}, "before": None}
        actions = transform(TOPIC_INVENTORY, event)

        assert len(actions) == 1
        assert isinstance(actions[0], IndexAction)

    def test_update_produces_index_action(self, item):
        event = {"op": "u", "after": {"id": item.pk, "deleted_at": None}, "before": None}
        actions = transform(TOPIC_INVENTORY, event)

        assert len(actions) == 1
        assert isinstance(actions[0], IndexAction)

    def test_soft_delete_produces_delete_action(self, item):
        event = {
            "op": "u",
            "after": {"id": item.pk, "deleted_at": "2026-03-27T00:00:00Z"},
            "before": None,
        }
        actions = transform(TOPIC_INVENTORY, event)

        assert len(actions) == 1
        assert isinstance(actions[0], DeleteAction)
        assert actions[0].doc_id == item.pk

    def test_delete_produces_delete_action(self, item):
        event = {"op": "d", "after": None, "before": {"id": item.pk}}
        actions = transform(TOPIC_INVENTORY, event)

        assert len(actions) == 1
        assert isinstance(actions[0], DeleteAction)

    def test_includes_product_fields(self, item, product):
        event = {"op": "c", "after": {"id": item.pk, "deleted_at": None}, "before": None}
        actions = transform(TOPIC_INVENTORY, event)

        doc = actions[0].document
        assert doc["product_name"] == "Aspirin"
        assert doc["product_sku"] == "ASP-100"

    def test_includes_drug_fields(self, item, drug):
        event = {"op": "c", "after": {"id": item.pk, "deleted_at": None}, "before": None}
        actions = transform(TOPIC_INVENTORY, event)

        doc = actions[0].document
        assert doc["drug_inn_name"] == "Acetylsalicylic acid"
        assert doc["drug_atc_code"] == "N02BA01"
        assert doc["drug_dosage_form"] == "tablet"

    def test_includes_location_fields(self, item):
        event = {"op": "c", "after": {"id": item.pk, "deleted_at": None}, "before": None}
        actions = transform(TOPIC_INVENTORY, event)

        doc = actions[0].document
        assert doc["location_name"] == "Warehouse A"
        assert doc["location_type"] == "warehouse"

    def test_missing_item_returns_empty(self, db):
        event = {"op": "c", "after": {"id": 99999, "deleted_at": None}, "before": None}
        actions = transform(TOPIC_INVENTORY, event)

        assert actions == [None]


@pytest.mark.unit
class TestProductTransform:
    def test_product_update_reindexes_items(self, item, product):
        event = {"op": "u", "after": {"id": product.pk, "sku": "ASP-100"}, "before": None}
        actions = transform(TOPIC_PRODUCT, event)

        assert len(actions) == 1
        assert isinstance(actions[0], IndexAction)
        assert actions[0].doc_id == item.pk

    def test_product_with_no_items_returns_empty(self, db):
        product = Product.objects.create(name="Orphan", sku="ORP-001", unit_price=Decimal("1.00"))
        event = {"op": "u", "after": {"id": product.pk, "sku": "ORP-001"}, "before": None}
        actions = transform(TOPIC_PRODUCT, event)

        assert actions == []


@pytest.mark.unit
class TestDrugTransform:
    def test_drug_update_reindexes_items(self, item, drug):
        event = {"op": "u", "after": {"product_id": drug.product_id}, "before": None}
        actions = transform(TOPIC_DRUG, event)

        assert len(actions) == 1
        assert isinstance(actions[0], IndexAction)


@pytest.mark.unit
class TestLocationTransform:
    def test_location_update_reindexes_items(self, item, location):
        event = {"op": "u", "after": {"id": location.pk}, "before": None}
        actions = transform(TOPIC_LOCATION, event)

        assert len(actions) == 1
        assert isinstance(actions[0], IndexAction)
        assert actions[0].doc_id == item.pk

    def test_location_with_no_items_returns_empty(self, db):
        loc = Location.objects.create(name="Empty", location_type="warehouse")
        event = {"op": "u", "after": {"id": loc.pk}, "before": None}
        actions = transform(TOPIC_LOCATION, event)

        assert actions == []


@pytest.mark.unit
class TestUnknownTopic:
    def test_unknown_topic_returns_empty(self):
        actions = transform("unknown.topic", {"op": "c", "after": {}})
        assert actions == []
