from unittest.mock import patch

import pytest
from django.urls import reverse

from apps.search.client import SearchUnavailable
from apps.search.contracts import LowStockItem, LowStockResult, StockBucket


def _result(items=None, by_location=None, by_category=None, total=0, out=0, threshold=10):
    return LowStockResult(
        threshold=threshold,
        total_items=total,
        out_of_stock=out,
        items=items or [],
        by_location=by_location or [],
        by_category=by_category or [],
        engine_took_ms=2,
    )


@pytest.mark.integration
@pytest.mark.django_db
class TestLowStockView:
    def test_renders_full_page_without_htmx_header(self, client):
        with patch("apps.search.views.services.low_stock", return_value=_result()):
            response = client.get(reverse("search:low-stock"))

        assert response.status_code == 200
        assert b"Low Stock" in response.content

    def test_renders_partial_with_htmx_header(self, client):
        items = [
            LowStockItem(
                id=1,
                item_name="Amoxil low",
                product_name="Amoxil",
                location_name="Karen",
                category="antibiotic",
                quantity=0,
                expiry_date="2026-09-12",
            )
        ]
        result = _result(
            items=items,
            by_location=[StockBucket(key="Karen", count=1)],
            by_category=[StockBucket(key="antibiotic", count=1)],
            total=1,
            out=1,
        )
        with patch("apps.search.views.services.low_stock", return_value=result):
            response = client.get(reverse("search:low-stock"), HTTP_HX_REQUEST="true")

        assert response.status_code == 200
        assert b"Amoxil low" in response.content
        assert b"Karen" in response.content
        assert b"antibiotic" in response.content
        assert b"<!DOCTYPE html" not in response.content

    def test_threshold_param_passes_through(self, client):
        with patch(
            "apps.search.views.services.low_stock", return_value=_result(threshold=5)
        ) as mock:
            client.get(reverse("search:low-stock"), {"threshold": "5"})

        passed = mock.call_args.args[0]
        assert passed.threshold == 5

    def test_invalid_threshold_falls_back_to_default(self, client):
        with patch("apps.search.views.services.low_stock", return_value=_result()) as mock:
            client.get(reverse("search:low-stock"), {"threshold": "abc"})

        assert mock.call_args.args[0].threshold == 10

    def test_search_unavailable_renders_card(self, client):
        with patch("apps.search.views.services.low_stock", side_effect=SearchUnavailable("down")):
            response = client.get(reverse("search:low-stock"), HTTP_HX_REQUEST="true")

        assert response.status_code == 200
        assert b"temporarily unavailable" in response.content

    def test_filters_passed_to_query(self, client):
        with patch("apps.search.views.services.low_stock", return_value=_result()) as mock:
            client.get(
                reverse("search:low-stock"),
                {"location": ["Westlands"], "category": ["antibiotic"]},
            )

        passed = mock.call_args.args[0]
        assert passed.location == ["Westlands"]
        assert passed.category == ["antibiotic"]
