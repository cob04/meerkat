from decimal import Decimal

import pytest

from apps.catalog.models import Drug, InventoryItem, Location, Product, StockMovement


@pytest.mark.unit
class TestProduct:
    def test_str_representation(self):
        product = Product(name="Bandage Roll", sku="BND-001", unit_price=Decimal("5.00"))
        assert str(product) == "Bandage Roll"

    def test_is_drug_false_when_no_drug_relation(self):
        product = Product(name="Bandage Roll", sku="BND-001", unit_price=Decimal("5.00"))
        assert product.is_drug is False


@pytest.mark.unit
class TestDrug:
    def test_str_representation(self):
        drug = Drug(inn_name="Metformin", strength="500", unit="mg")
        assert str(drug) == "Metformin 500mg"

    def test_dosage_form_choices(self):
        assert Drug.DosageForm.TABLET == "tablet"
        assert Drug.DosageForm.INJECTION == "injection"

    def test_storage_condition_choices(self):
        assert Drug.StorageCondition.REFRIGERATED == "refrigerated"
        assert Drug.StorageCondition.FROZEN == "frozen"


@pytest.mark.unit
class TestLocation:
    def test_str_representation(self):
        location = Location(
            name="Central Warehouse",
            location_type=Location.LocationType.WAREHOUSE,
        )
        assert str(location) == "Central Warehouse (Warehouse)"

    def test_location_type_choices(self):
        assert Location.LocationType.WAREHOUSE == "warehouse"
        assert Location.LocationType.PHARMACY == "pharmacy"
        assert Location.LocationType.WARD == "ward"


@pytest.mark.unit
class TestInventoryItem:
    def test_str_representation(self):
        location = Location(name="Main Pharmacy", location_type="pharmacy")
        item = InventoryItem(
            item_name="Metformin 500mg",
            location=location,
            batch_number="B2024-001",
            quantity=100,
            expiry_date="2026-06-15",
            unit_cost=Decimal("2.50"),
        )
        assert str(item) == "Metformin 500mg - B2024-001 @ Main Pharmacy"

    def test_is_cataloged_true_when_product_linked(self):
        item = InventoryItem(
            item_name="Test",
            batch_number="B001",
            quantity=10,
            expiry_date="2026-06-15",
            unit_cost=Decimal("1.00"),
        )
        item.product_id = 1
        assert item.is_cataloged is True

    def test_is_cataloged_false_when_no_product(self):
        item = InventoryItem(
            item_name="Test",
            batch_number="B001",
            quantity=10,
            expiry_date="2026-06-15",
            unit_cost=Decimal("1.00"),
        )
        assert item.is_cataloged is False

    def test_status_choices(self):
        assert InventoryItem.Status.AVAILABLE == "available"
        assert InventoryItem.Status.RECALLED == "recalled"
        assert InventoryItem.Status.EXPIRED == "expired"


@pytest.mark.unit
class TestStockMovement:
    def test_str_representation(self):
        location = Location(name="Main Pharmacy", location_type="pharmacy")
        item = InventoryItem(
            item_name="Metformin 500mg",
            location=location,
            batch_number="B2024-001",
            quantity=100,
            expiry_date="2026-06-15",
            unit_cost=Decimal("2.50"),
        )
        movement = StockMovement(
            inventory_item=item,
            movement_type=StockMovement.MovementType.RECEIVED,
            quantity=50,
        )
        assert "Received" in str(movement)
        assert "50" in str(movement)

    def test_movement_type_choices(self):
        assert StockMovement.MovementType.RECEIVED == "received"
        assert StockMovement.MovementType.DISPENSED == "dispensed"
        assert StockMovement.MovementType.TRANSFERRED == "transferred"
        assert StockMovement.MovementType.ADJUSTED == "adjusted"
        assert StockMovement.MovementType.RETURNED == "returned"
