from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse

from apps.catalog.models import InventoryItem, Location, Product, StockMovement

User = get_user_model()


@pytest.fixture
def user(db):
    return User.objects.create_user(username="testuser", password="testpass123")


@pytest.fixture
def client(user):
    c = Client()
    c.force_login(user)
    return c


@pytest.fixture
def location(db):
    return Location.objects.create(
        name="Main Warehouse", location_type=Location.LocationType.WAREHOUSE
    )


@pytest.fixture
def location_b(db):
    return Location.objects.create(name="Pharmacy B", location_type=Location.LocationType.PHARMACY)


@pytest.fixture
def item(location, user):
    item = InventoryItem.objects.create(
        item_name="Aspirin 100mg",
        location=location,
        batch_number="BATCH-001",
        quantity=100,
        expiry_date="2027-06-01",
        unit_cost=Decimal("5.50"),
    )
    StockMovement.objects.create(
        inventory_item=item,
        movement_type=StockMovement.MovementType.RECEIVED,
        quantity=100,
        to_location=location,
        performed_by=user,
    )
    return item


@pytest.mark.integration
class TestInventoryListView:
    def test_returns_200(self, client):
        response = client.get(reverse("catalog:inventory-list"))
        assert response.status_code == 200

    def test_htmx_returns_partial(self, client):
        response = client.get(
            reverse("catalog:inventory-list"),
            HTTP_HX_REQUEST="true",
        )
        assert response.status_code == 200
        assert b"<table" in response.content
        assert b"<!DOCTYPE" not in response.content

    def test_filters_by_status(self, client, item):
        response = client.get(
            reverse("catalog:inventory-list"),
            {"status": "available"},
        )
        assert response.status_code == 200
        assert b"Aspirin" in response.content

    def test_filters_exclude_nonmatching(self, client, item):
        response = client.get(
            reverse("catalog:inventory-list"),
            {"status": "recalled"},
        )
        assert response.status_code == 200
        assert b"Aspirin" not in response.content

    def test_search_by_name(self, client, item):
        response = client.get(
            reverse("catalog:inventory-list"),
            {"search": "Aspirin"},
        )
        assert b"Aspirin" in response.content

    def test_search_by_batch(self, client, item):
        response = client.get(
            reverse("catalog:inventory-list"),
            {"search": "BATCH-001"},
        )
        assert b"BATCH-001" in response.content


@pytest.mark.integration
class TestInventoryDetailView:
    def test_returns_200(self, client, item):
        response = client.get(reverse("catalog:inventory-detail", args=[item.pk]))
        assert response.status_code == 200
        assert b"Aspirin" in response.content

    def test_404_for_missing(self, client):
        response = client.get(reverse("catalog:inventory-detail", args=[99999]))
        assert response.status_code == 404

    def test_shows_movement_history(self, client, item):
        response = client.get(reverse("catalog:inventory-detail", args=[item.pk]))
        assert b"Received" in response.content


@pytest.mark.integration
class TestReceiveStockView:
    def test_get_returns_form(self, client):
        response = client.get(reverse("catalog:inventory-receive"))
        assert response.status_code == 200

    def test_post_valid_creates_item(self, client, location):
        response = client.post(
            reverse("catalog:inventory-receive"),
            {
                "item_name": "Ibuprofen 200mg",
                "location": location.pk,
                "batch_number": "IBU-001",
                "quantity": 25,
                "expiry_date": "2027-12-01",
                "unit_cost": "3.50",
            },
        )
        assert response.status_code == 302
        assert InventoryItem.objects.filter(batch_number="IBU-001").exists()

    def test_post_invalid_shows_errors(self, client):
        response = client.post(reverse("catalog:inventory-receive"), {})
        assert response.status_code == 200
        assert b"This field is required" in response.content


@pytest.mark.integration
class TestDispenseStockView:
    def test_get_returns_form(self, client, item):
        response = client.get(reverse("catalog:inventory-dispense", args=[item.pk]))
        assert response.status_code == 200

    def test_post_valid(self, client, item):
        response = client.post(
            reverse("catalog:inventory-dispense", args=[item.pk]),
            {"quantity": 10},
        )
        assert response.status_code == 302
        item.refresh_from_db()
        assert item.quantity == 90

    def test_post_exceeds_stock(self, client, item):
        response = client.post(
            reverse("catalog:inventory-dispense", args=[item.pk]),
            {"quantity": 999},
        )
        assert response.status_code == 200
        assert b"Insufficient stock" in response.content


@pytest.mark.integration
class TestTransferStockView:
    def test_get_returns_form(self, client, item):
        response = client.get(reverse("catalog:inventory-transfer", args=[item.pk]))
        assert response.status_code == 200

    def test_post_valid(self, client, item, location_b):
        response = client.post(
            reverse("catalog:inventory-transfer", args=[item.pk]),
            {"to_location": location_b.pk, "quantity": 20},
        )
        assert response.status_code == 302
        item.refresh_from_db()
        assert item.quantity == 80
        assert InventoryItem.objects.filter(location=location_b).exists()


@pytest.mark.integration
class TestAdjustStockView:
    def test_get_returns_form(self, client, item):
        response = client.get(reverse("catalog:inventory-adjust", args=[item.pk]))
        assert response.status_code == 200

    def test_post_valid(self, client, item):
        response = client.post(
            reverse("catalog:inventory-adjust", args=[item.pk]),
            {"new_quantity": 75, "reason": "Recount after audit"},
        )
        assert response.status_code == 302
        item.refresh_from_db()
        assert item.quantity == 75


@pytest.mark.integration
class TestReturnStockView:
    def test_get_returns_form(self, client, item):
        response = client.get(reverse("catalog:inventory-return", args=[item.pk]))
        assert response.status_code == 200

    def test_post_valid(self, client, item):
        response = client.post(
            reverse("catalog:inventory-return", args=[item.pk]),
            {"quantity": 5},
        )
        assert response.status_code == 302
        item.refresh_from_db()
        assert item.quantity == 105


@pytest.mark.integration
class TestRecallBatchView:
    def test_get_returns_form(self, client):
        response = client.get(reverse("catalog:inventory-recall"))
        assert response.status_code == 200

    def test_post_valid(self, client, item):
        response = client.post(
            reverse("catalog:inventory-recall"),
            {"batch_number": "BATCH-001", "reason": "Quality issue"},
        )
        assert response.status_code == 302
        item.refresh_from_db()
        assert item.status == InventoryItem.Status.RECALLED

    def test_post_unknown_batch(self, client):
        response = client.post(
            reverse("catalog:inventory-recall"),
            {"batch_number": "NOPE", "reason": "Test"},
        )
        assert response.status_code == 200
        assert b"No available inventory" in response.content


@pytest.mark.integration
class TestLocationListView:
    def test_returns_200(self, client, location):
        response = client.get(reverse("catalog:location-list"))
        assert response.status_code == 200
        assert b"Main Warehouse" in response.content


@pytest.mark.integration
class TestProductListView:
    def test_returns_200(self, client):
        Product.objects.create(name="Test Product", sku="TP-001", unit_price=Decimal("10.00"))
        response = client.get(reverse("catalog:product-list"))
        assert response.status_code == 200
        assert b"Test Product" in response.content
