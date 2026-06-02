from unittest.mock import patch

import pytest
from django.urls import reverse

from apps.search.client import SearchUnavailable
from apps.search.contracts import ForecastPoint, ValueAtRiskResult, ValueBucket


def _result():
    return ValueAtRiskResult(
        expired_value=5000.0,
        expiring_30d_value=1200.0,
        expiring_90d_value=8000.0,
        forecast=[ForecastPoint(month="2026-07", value=900.0, pct=100.0)],
        by_category=[ValueBucket(key="antibiotic", value=3000.0, quantity=90, items=10)],
        by_location=[ValueBucket(key="Karen Pharmacy", value=2000.0, quantity=60, items=8)],
        engine_took_ms=5,
    )


@pytest.mark.integration
@pytest.mark.django_db
class TestValueAtRiskView:
    def test_renders(self, client):
        with patch("apps.search.views.services.value_at_risk", return_value=_result()):
            response = client.get(reverse("search:value-at-risk"))

        assert response.status_code == 200
        body = response.content.decode()
        assert "Value at Risk" in body
        assert "Write-off forecast" in body
        assert "antibiotic" in body
        assert "2026-07" in body

    def test_unavailable(self, client):
        with patch(
            "apps.search.views.services.value_at_risk",
            side_effect=SearchUnavailable("down"),
        ):
            response = client.get(reverse("search:value-at-risk"))

        assert response.status_code == 200
        assert b"temporarily unavailable" in response.content
