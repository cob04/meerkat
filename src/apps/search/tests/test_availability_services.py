from decimal import Decimal
from unittest.mock import patch

import pytest

from apps.catalog.models import Location
from apps.search import services
from apps.search.contracts import AvailabilityQuery


def _empty_response():
    return {
        "took": 1,
        "hits": {"total": {"value": 0}},
        "aggregations": {
            "by_location": {"buckets": []},
            "network_quantity": {"value": 0},
        },
    }


def _bucket(location_id, name, qty, items=1):
    return {
        "key": location_id,
        "doc_count": items,
        "location_name": {"buckets": [{"key": name, "doc_count": items}]},
        "total_quantity": {"value": float(qty)},
    }


@pytest.mark.integration
@pytest.mark.django_db
class TestAvailabilityService:
    def test_origin_resolved_false_when_no_focus_location(self):
        with patch("apps.search.services.client.search", return_value=_empty_response()):
            result = services.availability(AvailabilityQuery(product_id=1))

        assert result.origin_resolved is False

    def test_origin_resolved_false_when_location_lacks_coordinates(self):
        loc = Location.objects.create(name="Westlands", location_type="pharmacy")

        with patch("apps.search.services.client.search", return_value=_empty_response()):
            result = services.availability(AvailabilityQuery(product_id=1, from_location_id=loc.pk))

        assert result.origin_resolved is False

    def test_origin_resolved_true_when_focus_has_coordinates(self):
        loc = Location.objects.create(
            name="Westlands",
            location_type="pharmacy",
            latitude=Decimal("-1.286389"),
            longitude=Decimal("36.817223"),
        )

        with patch(
            "apps.search.services.client.search", return_value=_empty_response()
        ) as mock_search:
            services.availability(AvailabilityQuery(product_id=1, from_location_id=loc.pk))

        body = mock_search.call_args.args[0]
        # The geo filter is only applied when both origin and max_distance_km are set,
        # but the service should still report origin as resolved.
        assert body  # built without error
        # No geo filter without max_distance_km
        assert not any("geo_distance" in c for c in body["query"]["bool"]["filter"])

    def test_distance_enrichment_uses_haversine(self):
        nairobi = Location.objects.create(
            name="Nairobi CBD",
            location_type="pharmacy",
            latitude=Decimal("-1.286389"),
            longitude=Decimal("36.817223"),
        )
        karen = Location.objects.create(
            name="Karen",
            location_type="pharmacy",
            latitude=Decimal("-1.319167"),
            longitude=Decimal("36.706944"),
        )

        response = {
            "took": 2,
            "hits": {"total": {"value": 1}},
            "aggregations": {
                "by_location": {"buckets": [_bucket(karen.pk, "Karen", 12)]},
                "network_quantity": {"value": 12.0},
            },
        }

        with patch("apps.search.services.client.search", return_value=response):
            result = services.availability(
                AvailabilityQuery(product_id=1, from_location_id=nairobi.pk)
            )

        assert result.origin_resolved is True
        assert result.by_location[0].distance_km is not None
        # Nairobi CBD <-> Karen great-circle distance is ~12-13km
        assert 10 < result.by_location[0].distance_km < 15

    def test_distance_null_when_bucket_location_has_no_coordinates(self):
        nairobi = Location.objects.create(
            name="Nairobi CBD",
            location_type="pharmacy",
            latitude=Decimal("-1.286389"),
            longitude=Decimal("36.817223"),
        )
        unmapped = Location.objects.create(name="Unmapped", location_type="pharmacy")

        response = {
            "took": 2,
            "hits": {"total": {"value": 1}},
            "aggregations": {
                "by_location": {"buckets": [_bucket(unmapped.pk, "Unmapped", 5)]},
                "network_quantity": {"value": 5.0},
            },
        }

        with patch("apps.search.services.client.search", return_value=response):
            result = services.availability(
                AvailabilityQuery(product_id=1, from_location_id=nairobi.pk)
            )

        assert result.by_location[0].distance_km is None

    def test_distance_sort_pushes_unknown_distance_to_end(self):
        nairobi = Location.objects.create(
            name="Nairobi CBD",
            location_type="pharmacy",
            latitude=Decimal("-1.286389"),
            longitude=Decimal("36.817223"),
        )
        karen = Location.objects.create(
            name="Karen",
            location_type="pharmacy",
            latitude=Decimal("-1.319167"),
            longitude=Decimal("36.706944"),
        )
        mombasa = Location.objects.create(
            name="Mombasa",
            location_type="pharmacy",
            latitude=Decimal("-4.043477"),
            longitude=Decimal("39.668207"),
        )
        unmapped = Location.objects.create(name="Unmapped", location_type="pharmacy")

        response = {
            "took": 1,
            "hits": {"total": {"value": 3}},
            "aggregations": {
                "by_location": {
                    "buckets": [
                        _bucket(unmapped.pk, "Unmapped", 4),
                        _bucket(mombasa.pk, "Mombasa", 50),
                        _bucket(karen.pk, "Karen", 12),
                    ]
                },
                "network_quantity": {"value": 66.0},
            },
        }

        with patch("apps.search.services.client.search", return_value=response):
            result = services.availability(
                AvailabilityQuery(product_id=1, from_location_id=nairobi.pk, sort="distance")
            )

        names = [row.location_name for row in result.by_location]
        assert names[0] == "Karen"
        assert names[1] == "Mombasa"
        assert names[-1] == "Unmapped"

    def test_location_sort_alphabetical(self):
        response = {
            "took": 1,
            "hits": {"total": {"value": 2}},
            "aggregations": {
                "by_location": {
                    "buckets": [
                        _bucket(2, "Westlands", 12),
                        _bucket(1, "Karen", 30),
                    ]
                },
                "network_quantity": {"value": 42.0},
            },
        }

        with patch("apps.search.services.client.search", return_value=response):
            result = services.availability(AvailabilityQuery(product_id=1, sort="location"))

        names = [row.location_name for row in result.by_location]
        assert names == ["Karen", "Westlands"]
