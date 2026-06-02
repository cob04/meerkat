from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
from django.contrib.auth import get_user_model

from apps.catalog.models import Drug, InventoryItem, Location, Product, StockMovement
from apps.catalog.services import (
    adjust_stock,
    dispense_stock,
    recall_batch,
    receive_stock,
    return_stock,
    search_locations,
    search_products,
    transfer_stock,
)

User = get_user_model()


def _mock_user():
    mock = MagicMock(spec=User)
    state = MagicMock()
    state.db = "default"
    mock._state = state
    mock.pk = 1
    return mock


def _mock_location(name="Main Pharmacy", pk=1):
    mock = MagicMock(spec=Location)
    mock.name = name
    mock.pk = pk
    mock._state = MagicMock(db="default")
    return mock


def _mock_item(quantity=100, status="available", location_name="Main Pharmacy", location_pk=1):
    item = MagicMock(spec=InventoryItem)
    item.pk = 42
    item.item_name = "Metformin 500mg"
    item.batch_number = "B2024-001"
    item.quantity = quantity
    item.status = status
    item.expiry_date = "2026-06-15"
    item.unit_cost = Decimal("2.50")
    item.product = None
    item.location = _mock_location(name=location_name, pk=location_pk)
    item.location_id = location_pk
    item._state = MagicMock(db="default")
    return item


@pytest.mark.unit
class TestReceiveStock:
    @patch("apps.catalog.services._log_event")
    @patch.object(StockMovement, "save")
    @patch.object(InventoryItem, "save")
    def test_creates_item_and_movement(self, mock_item_save, mock_movement_save, mock_log):
        user = _mock_user()
        location = _mock_location()

        result = receive_stock(
            item_name="Metformin 500mg",
            location=location,
            batch_number="B2024-001",
            quantity=100,
            expiry_date="2026-06-15",
            unit_cost=Decimal("2.50"),
            user=user,
        )

        assert result.item_name == "Metformin 500mg"
        assert result.quantity == 100
        mock_item_save.assert_called_once()
        mock_movement_save.assert_called_once()
        mock_log.assert_called_once()

    @patch("apps.catalog.services._log_event")
    @patch.object(StockMovement, "save")
    @patch.object(InventoryItem, "save")
    def test_accepts_optional_product(self, mock_item_save, mock_movement_save, mock_log):
        user = _mock_user()
        location = _mock_location()
        product = MagicMock(spec=Product)
        product._state = MagicMock(db="default")

        result = receive_stock(
            item_name="Test",
            location=location,
            batch_number="B001",
            quantity=50,
            expiry_date="2026-12-01",
            unit_cost=Decimal("1.00"),
            user=user,
            product=product,
        )

        assert result.product == product


@pytest.mark.unit
class TestDispenseStock:
    @patch("apps.catalog.services._log_event")
    @patch.object(StockMovement, "save")
    def test_reduces_quantity(self, mock_movement_save, mock_log):
        item = _mock_item(quantity=100)
        user = _mock_user()

        dispense_stock(item=item, quantity=30, user=user)

        assert item.quantity == 70
        item.save.assert_called_once_with(update_fields=["quantity", "updated_at"])

    @patch("apps.catalog.services._log_event")
    @patch.object(StockMovement, "save")
    def test_returns_movement(self, mock_movement_save, mock_log):
        item = _mock_item(quantity=100)
        user = _mock_user()

        result = dispense_stock(item=item, quantity=30, user=user)

        assert result.movement_type == StockMovement.MovementType.DISPENSED
        assert result.quantity == 30

    def test_rejects_unavailable_status(self):
        item = _mock_item(status="recalled")
        user = _mock_user()

        with pytest.raises(ValueError, match="status"):
            dispense_stock(item=item, quantity=10, user=user)

    def test_rejects_zero_quantity(self):
        item = _mock_item()
        user = _mock_user()

        with pytest.raises(ValueError, match="positive"):
            dispense_stock(item=item, quantity=0, user=user)

    def test_rejects_insufficient_stock(self):
        item = _mock_item(quantity=10)
        user = _mock_user()

        with pytest.raises(ValueError, match="Insufficient"):
            dispense_stock(item=item, quantity=20, user=user)


@pytest.mark.unit
class TestTransferStock:
    @patch("apps.catalog.services._log_event")
    @patch.object(StockMovement, "save")
    @patch.object(InventoryItem, "save")
    def test_reduces_source_and_creates_dest(self, mock_item_save, mock_movement_save, mock_log):
        item = _mock_item(quantity=100)
        dest = _mock_location(name="Ward A", pk=2)
        user = _mock_user()

        transfer_stock(item=item, to_location=dest, quantity=30, user=user)

        assert item.quantity == 70
        item.save.assert_called_once_with(update_fields=["quantity", "updated_at"])
        assert mock_item_save.call_count == 1

    @patch("apps.catalog.services._log_event")
    @patch.object(StockMovement, "save")
    @patch.object(InventoryItem, "save")
    def test_returns_transfer_movement(self, mock_item_save, mock_movement_save, mock_log):
        item = _mock_item(quantity=100)
        dest = _mock_location(name="Ward A", pk=2)
        user = _mock_user()

        result = transfer_stock(item=item, to_location=dest, quantity=30, user=user)

        assert result.movement_type == StockMovement.MovementType.TRANSFERRED
        assert result.quantity == 30

    def test_rejects_same_location(self):
        item = _mock_item(location_pk=1)
        dest = _mock_location(pk=1)
        user = _mock_user()

        with pytest.raises(ValueError, match="same"):
            transfer_stock(item=item, to_location=dest, quantity=10, user=user)

    def test_rejects_unavailable_status(self):
        item = _mock_item(status="expired")
        dest = _mock_location(pk=2)
        user = _mock_user()

        with pytest.raises(ValueError, match="status"):
            transfer_stock(item=item, to_location=dest, quantity=10, user=user)

    def test_rejects_insufficient_stock(self):
        item = _mock_item(quantity=10)
        dest = _mock_location(pk=2)
        user = _mock_user()

        with pytest.raises(ValueError, match="Insufficient"):
            transfer_stock(item=item, to_location=dest, quantity=20, user=user)


@pytest.mark.unit
class TestAdjustStock:
    @patch("apps.catalog.services._log_event")
    @patch.object(StockMovement, "save")
    def test_updates_quantity(self, mock_movement_save, mock_log):
        item = _mock_item(quantity=100)
        user = _mock_user()

        adjust_stock(item=item, new_quantity=80, reason="Physical count", user=user)

        assert item.quantity == 80
        item.save.assert_called_once_with(update_fields=["quantity", "updated_at"])

    @patch("apps.catalog.services._log_event")
    @patch.object(StockMovement, "save")
    def test_movement_records_difference(self, mock_movement_save, mock_log):
        item = _mock_item(quantity=100)
        user = _mock_user()

        result = adjust_stock(item=item, new_quantity=80, reason="Physical count", user=user)

        assert result.quantity == -20
        assert result.movement_type == StockMovement.MovementType.ADJUSTED

    def test_rejects_empty_reason(self):
        item = _mock_item()
        user = _mock_user()

        with pytest.raises(ValueError, match="Reason"):
            adjust_stock(item=item, new_quantity=80, reason="", user=user)

    def test_rejects_negative_quantity(self):
        item = _mock_item()
        user = _mock_user()

        with pytest.raises(ValueError, match="negative"):
            adjust_stock(item=item, new_quantity=-5, reason="Correction", user=user)


@pytest.mark.unit
class TestRecallBatch:
    @patch("apps.catalog.services._log_event")
    @patch.object(StockMovement, "save")
    def test_recalls_all_matching_items(self, mock_movement_save, mock_log):
        item1 = _mock_item(location_name="Warehouse", location_pk=1)
        item2 = _mock_item(location_name="Pharmacy", location_pk=2)

        with patch.object(
            InventoryItem.objects,
            "filter",
            return_value=MagicMock(select_related=MagicMock(return_value=[item1, item2])),
        ):
            user = _mock_user()
            result = recall_batch(batch_number="B2024-001", reason="Contamination", user=user)

        assert len(result) == 2
        assert item1.status == InventoryItem.Status.RECALLED
        assert item2.status == InventoryItem.Status.RECALLED
        assert item1.save.called
        assert item2.save.called

    def test_raises_when_no_items_found(self):
        with patch.object(
            InventoryItem.objects,
            "filter",
            return_value=MagicMock(select_related=MagicMock(return_value=[])),
        ):
            user = _mock_user()
            with pytest.raises(ValueError, match="No available inventory"):
                recall_batch(batch_number="NONEXISTENT", reason="Test", user=user)


@pytest.mark.unit
class TestReturnStock:
    @patch("apps.catalog.services._log_event")
    @patch.object(StockMovement, "save")
    def test_increases_quantity(self, mock_movement_save, mock_log):
        item = _mock_item(quantity=70)
        user = _mock_user()

        return_stock(item=item, quantity=30, user=user)

        assert item.quantity == 100
        item.save.assert_called_once_with(update_fields=["quantity", "updated_at"])

    @patch("apps.catalog.services._log_event")
    @patch.object(StockMovement, "save")
    def test_returns_return_movement(self, mock_movement_save, mock_log):
        item = _mock_item(quantity=70)
        user = _mock_user()

        result = return_stock(item=item, quantity=30, user=user)

        assert result.movement_type == StockMovement.MovementType.RETURNED
        assert result.quantity == 30

    def test_rejects_zero_quantity(self):
        item = _mock_item()
        user = _mock_user()

        with pytest.raises(ValueError, match="positive"):
            return_stock(item=item, quantity=0, user=user)

    def test_rejects_expired_stock(self):
        item = _mock_item(status="expired")
        user = _mock_user()

        with pytest.raises(ValueError, match="expired"):
            return_stock(item=item, quantity=10, user=user)


def _make_product(name, sku, category, active=True, drug=None):
    product = Product.objects.create(
        name=name, sku=sku, category=category, unit_price=Decimal("1.00"), is_active=active
    )
    if drug is not None:
        Drug.objects.create(
            product=product,
            inn_name=name,
            atc_code=drug.get("atc", "X00"),
            dosage_form=drug["dosage_form"],
            strength="500",
            unit="mg",
            requires_prescription=drug.get("rx", False),
        )
    return product


def _facet_counts(results, param):
    group = next(g for g in results.facets if g.param == param)
    return {opt.value: opt.count for opt in group.options}


@pytest.mark.integration
@pytest.mark.django_db
class TestSearchProducts:
    @pytest.fixture(autouse=True)
    def _catalog(self):
        _make_product(
            "Amoxicillin", "DRUG-1", "antibiotic", drug={"dosage_form": "tablet", "rx": True}
        )
        _make_product(
            "Paracetamol", "DRUG-2", "analgesic", drug={"dosage_form": "tablet", "rx": False}
        )
        _make_product(
            "Insulin", "DRUG-3", "diabetes", drug={"dosage_form": "injection", "rx": True}
        )
        _make_product("Surgical gloves", "SUP-1", "supplies")
        _make_product("Old device", "DEV-1", "devices", active=False)

    def test_returns_all_without_filters(self):
        assert search_products().total == 5

    def test_text_matches_name_or_sku(self):
        assert {p.name for p in search_products(q="amox").items} == {"Amoxicillin"}
        assert {p.name for p in search_products(q="sup-1").items} == {"Surgical gloves"}

    def test_category_filter(self):
        assert {p.name for p in search_products(categories=["antibiotic"]).items} == {"Amoxicillin"}

    def test_type_filter(self):
        assert search_products(types=["drug"]).total == 3
        assert search_products(types=["non_drug"]).total == 2

    def test_dosage_and_prescription_filters(self):
        assert {p.name for p in search_products(dosage_forms=["injection"]).items} == {"Insulin"}
        assert search_products(prescription=["yes"]).total == 2
        assert {p.name for p in search_products(prescription=["no"]).items} == {"Paracetamol"}

    def test_active_filter(self):
        assert {p.name for p in search_products(active=["no"]).items} == {"Old device"}

    def test_facet_counts_over_full_set(self):
        results = search_products()
        assert _facet_counts(results, "type") == {"drug": 3, "non_drug": 2}
        assert _facet_counts(results, "category")["antibiotic"] == 1

    def test_facet_counts_reflect_text_filter(self):
        results = search_products(q="insulin")
        assert _facet_counts(results, "type") == {"drug": 1, "non_drug": 0}


@pytest.mark.integration
@pytest.mark.django_db
class TestSearchLocations:
    @pytest.fixture(autouse=True)
    def _locations(self):
        Location.objects.create(
            name="Westlands Pharmacy",
            location_type=Location.LocationType.PHARMACY,
            latitude=Decimal("-1.2657"),
            longitude=Decimal("36.8124"),
        )
        Location.objects.create(
            name="Central Warehouse",
            location_type=Location.LocationType.WAREHOUSE,
            latitude=Decimal("-1.3000"),
            longitude=Decimal("36.8000"),
        )
        Location.objects.create(name="Ward A", location_type=Location.LocationType.WARD)

    def test_text_matches_name(self):
        assert {loc.name for loc in search_locations(q="ward").items} == {"Ward A"}

    def test_type_filter(self):
        assert {loc.name for loc in search_locations(types=["pharmacy"]).items} == {
            "Westlands Pharmacy"
        }

    def test_gps_filter(self):
        assert search_locations(gps=["yes"]).total == 2
        assert {loc.name for loc in search_locations(gps=["no"]).items} == {"Ward A"}

    def test_facet_counts(self):
        results = search_locations()
        assert _facet_counts(results, "type") == {"pharmacy": 1, "warehouse": 1, "ward": 1}
        assert _facet_counts(results, "gps") == {"yes": 2, "no": 1}
