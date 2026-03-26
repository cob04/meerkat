from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
from django.contrib.auth import get_user_model

from apps.catalog.models import InventoryItem, Location, Product, StockMovement
from apps.catalog.services import (
    adjust_stock,
    dispense_stock,
    recall_batch,
    receive_stock,
    return_stock,
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
