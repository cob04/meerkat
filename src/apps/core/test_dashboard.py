from datetime import timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from apps.catalog.models import InventoryItem, Location, StockMovement
from apps.core.services import dashboard_snapshot
from apps.search.client import SearchUnavailable

User = get_user_model()


def _low_stock(total):
    return SimpleNamespace(total_items=total)


def _rollup(count_30d):
    return SimpleNamespace(
        buckets=[
            SimpleNamespace(key="expired", count=0),
            SimpleNamespace(key="30d", count=count_30d),
        ]
    )


def _patch_search(low=0, expiring=0):
    return (
        patch("apps.core.services.search_services.low_stock", return_value=_low_stock(low)),
        patch("apps.core.services.search_services.expiry_rollup", return_value=_rollup(expiring)),
    )


@pytest.fixture
def user(db):
    return User.objects.create_user(username="dash", password="testpass123")


@pytest.fixture
def client(user):
    c = Client()
    c.force_login(user)
    return c


@pytest.fixture
def location(db):
    return Location.objects.create(
        name="Karen Pharmacy", location_type=Location.LocationType.PHARMACY
    )


def _item(location, **kwargs):
    defaults = {
        "item_name": "Item",
        "location": location,
        "batch_number": "B1",
        "quantity": 50,
        "expiry_date": timezone.localdate() + timedelta(days=200),
        "unit_cost": Decimal("1.00"),
        "status": InventoryItem.Status.AVAILABLE,
    }
    defaults.update(kwargs)
    return InventoryItem.objects.create(**defaults)


@pytest.mark.integration
@pytest.mark.django_db
class TestDashboardView:
    def test_root_url_resolves_to_dashboard(self, client, location):
        low, expiry = _patch_search()
        with low, expiry:
            response = client.get("/")

        assert response.status_code == 200
        assert response.resolver_match.view_name == "core:dashboard"
        assert b"Dashboard" in response.content

    def test_kpis_and_priority_questions_render(self, client, location):
        _item(location)
        low, expiry = _patch_search(low=4, expiring=7)
        with low, expiry:
            response = client.get(reverse("core:dashboard"))

        body = response.content.decode()
        assert "Total items" in body
        assert "Low stock" in body
        assert "Answer the five priority questions" in body

    def test_search_unavailable_still_renders(self, client, location):
        with patch(
            "apps.core.services.search_services.low_stock",
            side_effect=SearchUnavailable("down"),
        ):
            response = client.get(reverse("core:dashboard"))

        assert response.status_code == 200
        assert "Search index unavailable" in response.content.decode()

    def test_needs_attention_lists_problem_items(self, client, location):
        today = timezone.localdate()
        _item(location, item_name="Recalled item", status=InventoryItem.Status.RECALLED, quantity=5)
        _item(location, item_name="Low item", quantity=3)
        _item(location, item_name="Expiring item", expiry_date=today + timedelta(days=10))
        low, expiry = _patch_search()
        with low, expiry:
            response = client.get(reverse("core:dashboard"))

        body = response.content.decode()
        assert "Recalled item" in body
        assert "Low item" in body
        assert "Expiring item" in body

    def test_activity_feed_lists_recent_movements(self, client, location, user):
        item = _item(location)
        StockMovement.objects.create(
            inventory_item=item,
            movement_type=StockMovement.MovementType.DISPENSED,
            quantity=2,
            performed_by=user,
        )
        low, expiry = _patch_search()
        with low, expiry:
            response = client.get(reverse("core:dashboard"))

        assert "Dispensed" in response.content.decode()


@pytest.mark.integration
@pytest.mark.django_db
class TestDashboardSnapshot:
    def test_recall_kpis_aggregate(self, location):
        _item(location, status=InventoryItem.Status.RECALLED, quantity=5)
        _item(location, status=InventoryItem.Status.RECALLED, quantity=3)
        low, expiry = _patch_search()
        with low, expiry:
            snapshot = dashboard_snapshot()

        assert snapshot.kpis.active_recalls == 2
        assert snapshot.kpis.recalled_units == 8
        assert snapshot.kpis.recalled_locations == 1
        assert snapshot.search_ok is True

    def test_search_unavailable_nulls_search_kpis(self, location):
        with patch(
            "apps.core.services.search_services.low_stock",
            side_effect=SearchUnavailable("x"),
        ):
            snapshot = dashboard_snapshot()

        assert snapshot.search_ok is False
        assert snapshot.kpis.low_stock is None
        assert snapshot.kpis.expiring_30d is None

    def test_attention_deduplicates_items(self, location):
        today = timezone.localdate()
        _item(
            location,
            item_name="Low and expiring",
            quantity=2,
            expiry_date=today + timedelta(days=5),
        )
        low, expiry = _patch_search()
        with low, expiry:
            snapshot = dashboard_snapshot()

        names = [row.name for row in snapshot.attention]
        assert names.count("Low and expiring") == 1
