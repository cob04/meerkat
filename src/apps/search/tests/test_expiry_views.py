from unittest.mock import patch

import pytest
from django.urls import reverse

from apps.search.client import SearchUnavailable
from apps.search.contracts import EXPIRY_BUCKETS, ExpiryBucket, ExpiryRollup, LocationExpiry


def _empty_rollup():
    return ExpiryRollup(
        total_items=0,
        buckets=[ExpiryBucket(key=k, label=k, count=0) for k in EXPIRY_BUCKETS],
        by_location=[],
        by_category=[],
        engine_took_ms=2,
    )


@pytest.mark.integration
@pytest.mark.django_db
class TestExpiryView:
    def test_renders_full_page_without_htmx_header(self, client):
        with patch("apps.search.views.services.expiry_rollup", return_value=_empty_rollup()):
            response = client.get(reverse("search:expiry"))

        assert response.status_code == 200
        assert b"Expiry Dashboard" in response.content

    def test_renders_partial_with_htmx_header(self, client):
        rollup = ExpiryRollup(
            total_items=5,
            buckets=[
                ExpiryBucket(key="expired", label="Expired", count=2),
                ExpiryBucket(key="30d", label="Within 30 days", count=3),
                ExpiryBucket(key="90d", label="Within 90 days", count=0),
                ExpiryBucket(key="90plus", label="Over 90 days", count=0),
            ],
            by_location=[
                LocationExpiry(
                    location_name="Westlands",
                    total=2,
                    buckets=[
                        ExpiryBucket(key="expired", label="Expired", count=2),
                        ExpiryBucket(key="30d", label="Within 30 days", count=0),
                        ExpiryBucket(key="90d", label="Within 90 days", count=0),
                        ExpiryBucket(key="90plus", label="Over 90 days", count=0),
                    ],
                )
            ],
            by_category=[],
            engine_took_ms=4,
        )

        with patch("apps.search.views.services.expiry_rollup", return_value=rollup):
            response = client.get(reverse("search:expiry"), HTTP_HX_REQUEST="true")

        assert response.status_code == 200
        assert b"Westlands" in response.content
        assert b"Expired" in response.content
        assert b"<!DOCTYPE html" not in response.content

    def test_drilldown_link_carries_bucket(self, client):
        rollup = _empty_rollup()
        rollup.buckets[0] = ExpiryBucket(key="expired", label="Expired", count=2)

        with patch("apps.search.views.services.expiry_rollup", return_value=rollup):
            response = client.get(reverse("search:expiry"), HTTP_HX_REQUEST="true")

        assert b"expiry_bucket=expired" in response.content

    def test_search_unavailable_renders_card(self, client):
        with patch(
            "apps.search.views.services.expiry_rollup",
            side_effect=SearchUnavailable("down"),
        ):
            response = client.get(reverse("search:expiry"), HTTP_HX_REQUEST="true")

        assert response.status_code == 200
        assert b"temporarily unavailable" in response.content

    def test_passes_filters_to_query(self, client):
        with patch(
            "apps.search.views.services.expiry_rollup", return_value=_empty_rollup()
        ) as mock:
            client.get(
                reverse("search:expiry"),
                {"location": ["Westlands"], "category": ["antibiotic"]},
            )

        passed = mock.call_args.args[0]
        assert passed.location == ["Westlands"]
        assert passed.category == ["antibiotic"]
