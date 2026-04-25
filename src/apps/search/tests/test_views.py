from unittest.mock import patch

import pytest
from django.urls import reverse

from apps.search.client import SearchUnavailable
from apps.search.contracts import FacetBreakdown, InventoryDoc, InventoryResults


def _fake_results(items=None, total=0):
    return InventoryResults(
        items=items or [],
        total=total,
        page=1,
        page_size=25,
        engine_took_ms=7,
        facets=FacetBreakdown(),
    )


@pytest.mark.integration
@pytest.mark.django_db
class TestCatalogSearchView:
    def test_renders_full_page_without_htmx_header(self, client):
        with patch("apps.search.views.services.search_inventory", return_value=_fake_results()):
            response = client.get(reverse("search:catalog-search"), {"q": "panadol"})

        assert response.status_code == 200
        assert b"Catalog Search" in response.content
        assert b"Drug name, brand, batch" in response.content

    def test_renders_partial_with_htmx_header(self, client):
        item = InventoryDoc(
            id=1,
            item_name="Panadol 500mg",
            product_name="Panadol",
            batch_number="B1",
            location_name="Main",
            quantity=10,
            status="available",
            expiry_date="2027-01-01",
            score=1.0,
        )
        results = _fake_results(items=[item], total=1)

        with patch("apps.search.views.services.search_inventory", return_value=results):
            response = client.get(
                reverse("search:catalog-search"),
                {"q": "panadol"},
                HTTP_HX_REQUEST="true",
            )

        assert response.status_code == 200
        assert b"Panadol 500mg" in response.content
        assert b"<!DOCTYPE html" not in response.content

    def test_renders_unavailable_when_search_down(self, client):
        with patch(
            "apps.search.views.services.search_inventory",
            side_effect=SearchUnavailable("down"),
        ):
            response = client.get(
                reverse("search:catalog-search"),
                {"q": "panadol"},
                HTTP_HX_REQUEST="true",
            )

        assert response.status_code == 200
        assert b"temporarily unavailable" in response.content

    def test_blank_query_renders_without_search_call(self, client):
        with patch(
            "apps.search.views.services.search_inventory", return_value=_fake_results()
        ) as mock:
            response = client.get(reverse("search:catalog-search"))

        assert response.status_code == 200
        assert mock.call_count == 1
        assert mock.call_args.args[0].q is None

    def test_multi_value_facet_params_passed_to_query(self, client):
        with patch(
            "apps.search.views.services.search_inventory", return_value=_fake_results()
        ) as mock:
            client.get(
                reverse("search:catalog-search"),
                {
                    "q": "panadol",
                    "status": ["available", "reserved"],
                    "location": ["Main Pharmacy"],
                    "category": ["antibiotic"],
                },
            )

        passed = mock.call_args.args[0]
        assert passed.status == ["available", "reserved"]
        assert passed.location == ["Main Pharmacy"]
        assert passed.category == ["antibiotic"]

    def test_base_qs_strips_page(self, client):
        item = InventoryDoc(
            id=1,
            item_name="x",
            product_name=None,
            batch_number="B",
            location_name=None,
            quantity=0,
            status="available",
            expiry_date=None,
        )
        results = InventoryResults(
            items=[item],
            total=60,
            page=2,
            page_size=25,
            engine_took_ms=1,
            facets=FacetBreakdown(),
        )

        with patch("apps.search.views.services.search_inventory", return_value=results):
            response = client.get(
                reverse("search:catalog-search"),
                {"q": "p", "page": "2", "status": "available"},
                HTTP_HX_REQUEST="true",
            )

        body = response.content.decode()
        assert "q=p" in body
        assert "status=available" in body
        assert "&page=" in body
        assert "page=2&" not in body and "&page=2" not in body
