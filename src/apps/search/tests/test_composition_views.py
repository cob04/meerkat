from unittest.mock import patch

import pytest
from django.urls import reverse

from apps.search.client import SearchUnavailable
from apps.search.contracts import CompositionResult, ValueBucket


def _result():
    return CompositionResult(
        total_value=125000.0,
        top_manufacturer="GSK",
        supplier_concentration=32.0,
        by_manufacturer=[ValueBucket(key="GSK", value=40000.0, quantity=900, items=20)],
        by_atc_class=[
            ValueBucket(key="Cardiovascular system", value=20000.0, quantity=400, items=10)
        ],
        by_dosage_form=[ValueBucket(key="Tablet", value=60000.0, quantity=1500, items=30)],
        by_prescription=[
            ValueBucket(key="Prescription required", value=90000.0, quantity=2000, items=40)
        ],
        engine_took_ms=5,
    )


@pytest.mark.integration
@pytest.mark.django_db
class TestCatalogCompositionView:
    def test_renders(self, client):
        with patch("apps.search.views.services.catalog_composition", return_value=_result()):
            response = client.get(reverse("search:catalog-composition"))

        assert response.status_code == 200
        body = response.content.decode()
        assert "Catalog Composition" in body
        assert "GSK" in body
        assert "Cardiovascular system" in body
        assert "32.0%" in body

    def test_unavailable(self, client):
        with patch(
            "apps.search.views.services.catalog_composition",
            side_effect=SearchUnavailable("down"),
        ):
            response = client.get(reverse("search:catalog-composition"))

        assert response.status_code == 200
        assert b"temporarily unavailable" in response.content
