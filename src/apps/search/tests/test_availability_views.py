from unittest.mock import patch

import pytest
from django.urls import reverse

from apps.search.client import SearchUnavailable
from apps.search.contracts import AvailabilityResult, LocationStock


def _result(rows=None, origin=False):
    rows = rows or []
    return AvailabilityResult(
        product_id=1,
        drug_id=None,
        total_quantity=sum(r.quantity for r in rows),
        total_items=sum(r.item_count for r in rows),
        by_location=rows,
        engine_took_ms=3,
        origin_resolved=origin,
    )


@pytest.mark.integration
@pytest.mark.django_db
class TestAvailabilityView:
    def test_renders_full_page_without_htmx_header(self, client):
        with patch("apps.search.views.services.availability", return_value=_result()):
            response = client.get(reverse("search:availability"), {"product_id": "1"})

        assert response.status_code == 200
        assert b"Cross-location Availability" in response.content

    def test_renders_partial_with_htmx_header(self, client):
        rows = [LocationStock(location_id=1, location_name="Karen", quantity=12, item_count=1)]
        with patch("apps.search.views.services.availability", return_value=_result(rows)):
            response = client.get(
                reverse("search:availability"),
                {"product_id": "1"},
                HTTP_HX_REQUEST="true",
            )

        assert response.status_code == 200
        assert b"Karen" in response.content
        assert b"<!DOCTYPE html" not in response.content

    def test_missing_target_renders_error(self, client):
        response = client.get(reverse("search:availability"))

        assert response.status_code == 200
        assert b"product_id" in response.content
        assert b"drug_id" in response.content

    def test_invalid_target_renders_error(self, client):
        response = client.get(reverse("search:availability"), {"product_id": "abc"})

        assert response.status_code == 200
        assert b"product_id" in response.content

    def test_search_unavailable_renders_unavailable_card(self, client):
        with patch(
            "apps.search.views.services.availability",
            side_effect=SearchUnavailable("down"),
        ):
            response = client.get(
                reverse("search:availability"),
                {"product_id": "1"},
                HTTP_HX_REQUEST="true",
            )

        assert response.status_code == 200
        assert b"temporarily unavailable" in response.content

    def test_passes_focus_and_radius_to_service(self, client):
        with patch("apps.search.views.services.availability", return_value=_result()) as mock:
            client.get(
                reverse("search:availability"),
                {
                    "product_id": "1",
                    "from_location_id": "10",
                    "max_distance_km": "50",
                    "sort": "distance",
                },
            )

        passed = mock.call_args.args[0]
        assert passed.product_id == 1
        assert passed.from_location_id == 10
        assert passed.max_distance_km == 50
        assert passed.sort == "distance"

    def test_invalid_sort_falls_back_to_default(self, client):
        with patch("apps.search.views.services.availability", return_value=_result()) as mock:
            client.get(
                reverse("search:availability"),
                {"product_id": "1", "sort": "bogus"},
            )

        passed = mock.call_args.args[0]
        assert passed.sort == "-quantity"

    def test_warning_shown_when_focus_lacks_coordinates(self, client):
        with patch(
            "apps.search.views.services.availability",
            return_value=_result(origin=False),
        ):
            response = client.get(
                reverse("search:availability"),
                {"product_id": "1", "from_location_id": "10"},
                HTTP_HX_REQUEST="true",
            )

        assert b"distance unavailable" in response.content
