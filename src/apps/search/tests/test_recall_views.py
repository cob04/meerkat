from unittest.mock import patch

import pytest
from django.urls import reverse

from apps.search.client import SearchUnavailable
from apps.search.contracts import RecallBucket, RecallImpact, RecallMatch


def _impact(matches=None, by_location=None, total=0, qty=0):
    return RecallImpact(
        total_items=total,
        total_quantity=qty,
        matches=matches or [],
        by_location=by_location or [],
        engine_took_ms=2,
    )


@pytest.mark.integration
@pytest.mark.django_db
class TestRecallLookupView:
    def test_renders_full_page_without_htmx_header(self, client):
        response = client.get(reverse("search:recall-lookup"))

        assert response.status_code == 200
        assert b"Recall Lookup" in response.content
        assert b"at least one criterion" in response.content

    def test_no_criteria_skips_service_call(self, client):
        with patch("apps.search.views.services.recall_impact") as mock:
            client.get(reverse("search:recall-lookup"))

        mock.assert_not_called()

    def test_renders_partial_with_htmx_header(self, client):
        match = RecallMatch(
            id=10,
            item_name="Lantus 100IU",
            product_name="Lantus",
            drug_inn_name="Insulin glargine",
            manufacturer="Sanofi",
            batch_number="B5421",
            location_name="Karen Pharmacy",
            quantity=12,
            status="available",
            expiry_date="2026-12-01",
        )
        result = _impact(
            matches=[match],
            by_location=[RecallBucket(location_name="Karen Pharmacy", item_count=1, quantity=12)],
            total=1,
            qty=12,
        )
        with patch("apps.search.views.services.recall_impact", return_value=result):
            response = client.get(
                reverse("search:recall-lookup"),
                {"manufacturer": "Sanofi"},
                HTTP_HX_REQUEST="true",
            )

        assert response.status_code == 200
        assert b"Lantus 100IU" in response.content
        assert b"Karen Pharmacy" in response.content
        assert b"<!DOCTYPE html" not in response.content

    def test_criteria_passed_to_service(self, client):
        with patch("apps.search.views.services.recall_impact", return_value=_impact()) as mock:
            client.get(
                reverse("search:recall-lookup"),
                {
                    "manufacturer": "Pfizer",
                    "batch_pattern": "B5*",
                    "drug_id": "7",
                    "created_from": "2026-01-01",
                    "created_to": "2026-04-30",
                },
            )

        passed = mock.call_args.args[0]
        assert passed.manufacturer == "Pfizer"
        assert passed.batch_pattern == "B5*"
        assert passed.drug_id == 7
        assert passed.created_from == "2026-01-01"
        assert passed.created_to == "2026-04-30"

    def test_blank_strings_treated_as_none(self, client):
        with patch("apps.search.views.services.recall_impact", return_value=_impact()) as mock:
            client.get(
                reverse("search:recall-lookup"),
                {"manufacturer": "  ", "batch_pattern": ""},
            )

        # No criteria => service is not called
        mock.assert_not_called()

    def test_search_unavailable_renders_card(self, client):
        with patch(
            "apps.search.views.services.recall_impact",
            side_effect=SearchUnavailable("down"),
        ):
            response = client.get(
                reverse("search:recall-lookup"),
                {"manufacturer": "Sanofi"},
                HTTP_HX_REQUEST="true",
            )

        assert response.status_code == 200
        assert b"temporarily unavailable" in response.content
