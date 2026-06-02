from unittest.mock import patch

import pytest
from django.urls import reverse

from apps.search.client import SearchUnavailable
from apps.search.contracts import DeadStockRow, MoverRow, ThroughputPoint, TurnoverResult


def _result():
    return TurnoverResult(
        window_days=30,
        dispensed_units=420,
        received_units=900,
        dead_stock_value=12500.0,
        throughput=[ThroughputPoint(period="2026-05-25", dispensed=30, received=80)],
        top_movers=[MoverRow(product="Panadol", units=50)],
        dead_stock=[DeadStockRow(product="Lantus", units=40, value=800.0)],
        engine_took_ms=7,
    )


@pytest.mark.integration
@pytest.mark.django_db
class TestTurnoverView:
    def test_renders(self, client):
        with patch("apps.search.views.services.turnover", return_value=_result()):
            response = client.get(reverse("search:turnover"))

        assert response.status_code == 200
        body = response.content.decode()
        assert "Turnover" in body
        assert "Top movers" in body
        assert "Panadol" in body
        assert "Lantus" in body

    def test_unavailable(self, client):
        with patch("apps.search.views.services.turnover", side_effect=SearchUnavailable("down")):
            response = client.get(reverse("search:turnover"))

        assert response.status_code == 200
        assert b"temporarily unavailable" in response.content
