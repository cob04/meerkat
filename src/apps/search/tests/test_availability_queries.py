import pytest

from apps.search.contracts import AvailabilityQuery
from apps.search.queries import availability


@pytest.mark.unit
class TestAvailabilityQueryContract:
    def test_requires_target(self):
        with pytest.raises(ValueError):
            AvailabilityQuery()

    def test_default_sort_with_origin_is_distance(self):
        q = AvailabilityQuery(product_id=1, from_location_id=10)

        assert q.sort == "distance"

    def test_default_sort_without_origin_is_quantity_desc(self):
        q = AvailabilityQuery(product_id=1)

        assert q.sort == "-quantity"

    def test_rejects_unknown_sort(self):
        with pytest.raises(ValueError):
            AvailabilityQuery(product_id=1, sort="random")


@pytest.mark.unit
class TestBuildBody:
    def test_must_includes_product_id_when_present(self):
        body = availability.build_body(AvailabilityQuery(product_id=42))

        assert {"term": {"product_id": 42}} in body["query"]["bool"]["must"]

    def test_must_includes_drug_id_when_present(self):
        body = availability.build_body(AvailabilityQuery(drug_id=7))

        assert {"term": {"drug_id": 7}} in body["query"]["bool"]["must"]

    def test_filters_to_available_in_stock(self):
        body = availability.build_body(AvailabilityQuery(product_id=1))

        filters = body["query"]["bool"]["filter"]
        assert {"term": {"status": "available"}} in filters
        assert {"range": {"quantity": {"gt": 0}}} in filters

    def test_no_geo_filter_without_origin(self):
        body = availability.build_body(
            AvailabilityQuery(product_id=1, max_distance_km=10), origin=None
        )

        assert not any("geo_distance" in clause for clause in body["query"]["bool"]["filter"])

    def test_no_geo_filter_without_max_distance(self):
        body = availability.build_body(
            AvailabilityQuery(product_id=1, from_location_id=10),
            origin={"lat": 0.0, "lon": 0.0},
        )

        assert not any("geo_distance" in clause for clause in body["query"]["bool"]["filter"])

    def test_geo_filter_when_origin_and_radius_provided(self):
        body = availability.build_body(
            AvailabilityQuery(product_id=1, from_location_id=10, max_distance_km=25),
            origin={"lat": -1.28, "lon": 36.81},
        )

        filters = body["query"]["bool"]["filter"]
        assert any(clause.get("geo_distance", {}).get("distance") == "25km" for clause in filters)

    def test_size_zero_no_hits(self):
        body = availability.build_body(AvailabilityQuery(product_id=1))

        assert body["size"] == 0

    def test_terms_agg_on_location_id(self):
        body = availability.build_body(AvailabilityQuery(product_id=1))

        terms = body["aggs"]["by_location"]["terms"]
        assert terms["field"] == "location_id"
        assert terms["size"] == availability.LOCATION_BUCKET_SIZE

    def test_quantity_sort_orders_by_total_quantity(self):
        body = availability.build_body(AvailabilityQuery(product_id=1, sort="-quantity"))

        order = body["aggs"]["by_location"]["terms"]["order"]
        assert order == {"total_quantity": "desc"}

    def test_distance_sort_uses_count_order_in_query(self):
        # distance sort happens in Python after parse; the OS-side bucket order
        # falls back to count to keep top-N stable when truncated.
        body = availability.build_body(
            AvailabilityQuery(product_id=1, from_location_id=10, sort="distance")
        )

        assert body["aggs"]["by_location"]["terms"]["order"] == {"_count": "desc"}


@pytest.mark.unit
class TestParseResponse:
    def test_extracts_bucket_into_location_stock(self):
        response = {
            "took": 12,
            "hits": {"total": {"value": 4}},
            "aggregations": {
                "by_location": {
                    "buckets": [
                        {
                            "key": 1,
                            "doc_count": 3,
                            "location_name": {"buckets": [{"key": "Westlands", "doc_count": 3}]},
                            "total_quantity": {"value": 120.0},
                        },
                        {
                            "key": 2,
                            "doc_count": 1,
                            "location_name": {"buckets": [{"key": "Karen", "doc_count": 1}]},
                            "total_quantity": {"value": 12.0},
                        },
                    ]
                },
                "network_quantity": {"value": 132.0},
            },
        }

        result = availability.parse_response(
            response, AvailabilityQuery(product_id=1, sort="-quantity")
        )

        assert result.product_id == 1
        assert result.total_quantity == 132
        assert result.total_items == 4
        assert result.engine_took_ms == 12
        assert len(result.by_location) == 2
        assert result.by_location[0].location_id == 1
        assert result.by_location[0].location_name == "Westlands"
        assert result.by_location[0].quantity == 120
        assert result.by_location[0].item_count == 3
        assert result.by_location[0].distance_km is None

    def test_handles_missing_location_name_bucket(self):
        response = {
            "took": 1,
            "hits": {"total": {"value": 1}},
            "aggregations": {
                "by_location": {
                    "buckets": [
                        {
                            "key": 9,
                            "doc_count": 1,
                            "location_name": {"buckets": []},
                            "total_quantity": {"value": 4.0},
                        }
                    ]
                },
                "network_quantity": {"value": 4.0},
            },
        }

        result = availability.parse_response(response, AvailabilityQuery(product_id=1))

        assert result.by_location[0].location_name == ""
