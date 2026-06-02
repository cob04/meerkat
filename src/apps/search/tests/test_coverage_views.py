from unittest.mock import patch

import pytest
from django.urls import reverse

from apps.search.client import SearchUnavailable
from apps.search.contracts import CoverageBand, CoverageResult, SingleSourceProduct


def _result():
    return CoverageResult(
        products_in_stock=20,
        single_source_count=4,
        well_covered_count=11,
        coverage_bands=[
            CoverageBand(label="1 site", products=4),
            CoverageBand(label="2 sites", products=5),
            CoverageBand(label="3+ sites", products=11),
        ],
        single_source=[
            SingleSourceProduct(product="Lantus", site="Karen Pharmacy", units=40, value=800.0)
        ],
        engine_took_ms=6,
    )


@pytest.mark.integration
@pytest.mark.django_db
class TestNetworkCoverageView:
    def test_renders(self, client):
        with patch("apps.search.views.services.network_coverage", return_value=_result()):
            response = client.get(reverse("search:network-coverage"))

        assert response.status_code == 200
        body = response.content.decode()
        assert "Network Coverage" in body
        assert "Single-source products" in body
        assert "Lantus" in body
        assert "Karen Pharmacy" in body

    def test_unavailable(self, client):
        with patch(
            "apps.search.views.services.network_coverage",
            side_effect=SearchUnavailable("down"),
        ):
            response = client.get(reverse("search:network-coverage"))

        assert response.status_code == 200
        assert b"temporarily unavailable" in response.content
