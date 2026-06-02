from unittest.mock import patch

import pytest
from django.urls import reverse

from apps.search.client import SearchUnavailable
from apps.search.contracts import ValueBucket, ValueResult


def _result():
    return ValueResult(
        total_value=125000.0,
        total_quantity=4200,
        total_items=180,
        by_location=[ValueBucket(key="Karen Pharmacy", value=60000.0, quantity=2000, items=40)],
        by_category=[ValueBucket(key="antibiotic", value=30000.0, quantity=900, items=20)],
        by_manufacturer=[ValueBucket(key="GSK", value=20000.0, quantity=600, items=12)],
        engine_took_ms=4,
    )


@pytest.mark.integration
@pytest.mark.django_db
class TestInventoryValueView:
    def test_renders_value_dashboard(self, client):
        with patch("apps.search.views.services.inventory_value", return_value=_result()):
            response = client.get(reverse("search:inventory-value"))

        assert response.status_code == 200
        body = response.content.decode()
        assert "Inventory Value" in body
        assert "Karen Pharmacy" in body
        assert "125,000" in body

    def test_unavailable_renders_message(self, client):
        with patch(
            "apps.search.views.services.inventory_value",
            side_effect=SearchUnavailable("down"),
        ):
            response = client.get(reverse("search:inventory-value"))

        assert response.status_code == 200
        assert b"temporarily unavailable" in response.content
