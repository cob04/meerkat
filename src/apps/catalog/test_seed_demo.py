import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command

from apps.catalog.models import Drug, InventoryItem, Location, Product, StockMovement
from apps.core.models import AuditEvent


@pytest.mark.integration
@pytest.mark.django_db
class TestSeedDemoCommand:
    def test_creates_locations_with_some_gps_pins(self):
        call_command("seed_demo", "--items=10")

        assert Location.objects.count() >= 5
        assert Location.objects.filter(latitude__isnull=False).count() >= 5

    def test_creates_drugs_and_non_drug_products(self):
        call_command("seed_demo", "--items=10")

        assert Drug.objects.count() >= 10
        # Some products are not drugs
        assert Product.objects.filter(drug__isnull=True).exists()

    def test_creates_inventory_spanning_statuses_and_buckets(self):
        call_command("seed_demo", "--items=200")

        statuses = set(InventoryItem.objects.values_list("status", flat=True))
        assert {"available", "expired", "recalled"}.issubset(statuses)

    def test_repeatable_with_seed(self):
        call_command("seed_demo", "--items=20", "--seed=7")
        first = InventoryItem.objects.count()
        call_command("seed_demo", "--items=20", "--seed=7", "--reset")
        second = InventoryItem.objects.count()

        assert first == second

    def test_reset_wipes_existing(self):
        call_command("seed_demo", "--items=10")
        before = InventoryItem.objects.count()
        call_command("seed_demo", "--items=5", "--reset")
        after = InventoryItem.objects.count()

        assert before > 0
        assert after == 5

    def test_seeds_movement_and_audit_history(self):
        call_command("seed_demo", "--items=20")

        assert StockMovement.objects.exists()
        assert AuditEvent.objects.exists()
        assert get_user_model().objects.filter(username="demo").exists()

    def test_reset_clears_movements(self):
        call_command("seed_demo", "--items=10")
        assert StockMovement.objects.exists()
        call_command("seed_demo", "--items=5", "--reset")

        assert StockMovement.objects.count() > 0
        assert StockMovement.objects.filter(inventory_item__isnull=True).count() == 0
