from decimal import Decimal

import pytest

from apps.catalog.forms import (
    AdjustStockForm,
    DispenseStockForm,
    InventoryFilterForm,
    RecallBatchForm,
    ReceiveStockForm,
    ReturnStockForm,
    TransferStockForm,
)
from apps.catalog.models import Location


@pytest.mark.unit
class TestReceiveStockForm:
    @pytest.fixture(autouse=True)
    def setup(self, db):
        self.location = Location.objects.create(
            name="Warehouse A", location_type=Location.LocationType.WAREHOUSE
        )

    def test_valid_data(self):
        form = ReceiveStockForm(
            data={
                "item_name": "Aspirin 100mg",
                "location": self.location.pk,
                "batch_number": "BATCH-001",
                "quantity": 50,
                "expiry_date": "2027-01-01",
                "unit_cost": "5.99",
            }
        )
        assert form.is_valid()

    def test_missing_required_fields(self):
        form = ReceiveStockForm(data={})
        assert not form.is_valid()
        assert "item_name" in form.errors
        assert "location" in form.errors
        assert "batch_number" in form.errors
        assert "quantity" in form.errors
        assert "expiry_date" in form.errors
        assert "unit_cost" in form.errors

    def test_quantity_must_be_positive(self):
        form = ReceiveStockForm(
            data={
                "item_name": "Test",
                "location": self.location.pk,
                "batch_number": "B1",
                "quantity": 0,
                "expiry_date": "2027-01-01",
                "unit_cost": "1.00",
            }
        )
        assert not form.is_valid()
        assert "quantity" in form.errors

    def test_product_is_optional(self):
        form = ReceiveStockForm(
            data={
                "item_name": "Test",
                "location": self.location.pk,
                "batch_number": "B1",
                "quantity": 10,
                "expiry_date": "2027-01-01",
                "unit_cost": "1.00",
            }
        )
        assert form.is_valid()
        assert form.cleaned_data["product"] is None


@pytest.mark.unit
class TestDispenseStockForm:
    def test_valid(self):
        form = DispenseStockForm(data={"quantity": 5})
        assert form.is_valid()

    def test_zero_rejected(self):
        form = DispenseStockForm(data={"quantity": 0})
        assert not form.is_valid()


@pytest.mark.unit
class TestTransferStockForm:
    @pytest.fixture(autouse=True)
    def setup(self, db):
        self.loc_a = Location.objects.create(
            name="Loc A", location_type=Location.LocationType.WAREHOUSE
        )
        self.loc_b = Location.objects.create(
            name="Loc B", location_type=Location.LocationType.PHARMACY
        )

    def test_valid(self):
        form = TransferStockForm(data={"to_location": self.loc_b.pk, "quantity": 10})
        assert form.is_valid()

    def test_excludes_current_location(self):
        form = TransferStockForm(
            data={"to_location": self.loc_a.pk, "quantity": 10},
            exclude_location=self.loc_a,
        )
        assert not form.is_valid()
        assert "to_location" in form.errors


@pytest.mark.unit
class TestAdjustStockForm:
    def test_valid(self):
        form = AdjustStockForm(data={"new_quantity": 10, "reason": "Recount"})
        assert form.is_valid()

    def test_reason_required(self):
        form = AdjustStockForm(data={"new_quantity": 10})
        assert not form.is_valid()
        assert "reason" in form.errors

    def test_negative_quantity_rejected(self):
        form = AdjustStockForm(data={"new_quantity": -1, "reason": "Oops"})
        assert not form.is_valid()


@pytest.mark.unit
class TestReturnStockForm:
    def test_valid(self):
        form = ReturnStockForm(data={"quantity": 3})
        assert form.is_valid()

    def test_zero_rejected(self):
        form = ReturnStockForm(data={"quantity": 0})
        assert not form.is_valid()


@pytest.mark.unit
class TestRecallBatchForm:
    def test_valid(self):
        form = RecallBatchForm(data={"batch_number": "BATCH-001", "reason": "Contamination"})
        assert form.is_valid()

    def test_missing_fields(self):
        form = RecallBatchForm(data={})
        assert not form.is_valid()
        assert "batch_number" in form.errors
        assert "reason" in form.errors


@pytest.mark.unit
class TestInventoryFilterForm:
    def test_empty_is_valid(self):
        form = InventoryFilterForm(data={})
        assert form.is_valid()

    def test_with_status(self):
        form = InventoryFilterForm(data={"status": "available"})
        assert form.is_valid()
