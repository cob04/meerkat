import math

from apps.catalog.models import Location
from apps.search import client
from apps.search.contracts import (
    AvailabilityQuery,
    AvailabilityResult,
    ExpiryQuery,
    ExpiryRollup,
    InventoryQuery,
    InventoryResults,
    LowStockResult,
    RecallImpact,
    RecallQuery,
    StockQuery,
)
from apps.search.queries import availability as availability_query
from apps.search.queries import expiry as expiry_query
from apps.search.queries import recall as recall_query
from apps.search.queries import search as search_query
from apps.search.queries import stock as stock_query

EARTH_RADIUS_KM = 6371.0088


def search_inventory(query: InventoryQuery) -> InventoryResults:
    body = search_query.build_body(query)
    response = client.search(body)
    return search_query.parse_response(response, query)


def expiry_rollup(query: ExpiryQuery) -> ExpiryRollup:
    body = expiry_query.build_body(query)
    response = client.search(body)
    return expiry_query.parse_response(response)


def low_stock(query: StockQuery) -> LowStockResult:
    body = stock_query.build_body(query)
    response = client.search(body)
    return stock_query.parse_response(response, query)


def recall_impact(query: RecallQuery) -> RecallImpact:
    body = recall_query.build_body(query)
    response = client.search(body)
    return recall_query.parse_response(response)


def availability(query: AvailabilityQuery) -> AvailabilityResult:
    origin = _resolve_origin(query.from_location_id)
    body = availability_query.build_body(query, origin=origin)
    response = client.search(body)
    result = availability_query.parse_response(response, query)
    result.origin_resolved = origin is not None
    if origin and result.by_location:
        _enrich_with_distance(result, origin)
    _apply_local_sort(result, query.sort)
    return result


def _resolve_origin(location_id: int | None) -> dict | None:
    if not location_id:
        return None
    try:
        location = Location.objects.only("latitude", "longitude").get(pk=location_id)
    except Location.DoesNotExist:
        return None
    if not location.has_coordinates:
        return None
    return {"lat": float(location.latitude), "lon": float(location.longitude)}


def _enrich_with_distance(result: AvailabilityResult, origin: dict) -> None:
    location_ids = [row.location_id for row in result.by_location]
    locations = Location.objects.filter(pk__in=location_ids).only("id", "latitude", "longitude")
    coords = {
        loc.pk: (float(loc.latitude), float(loc.longitude))
        for loc in locations
        if loc.has_coordinates
    }
    for row in result.by_location:
        pair = coords.get(row.location_id)
        if pair is None:
            continue
        row.distance_km = round(_haversine(origin["lat"], origin["lon"], pair[0], pair[1]), 2)


def _apply_local_sort(result: AvailabilityResult, sort: str) -> None:
    if sort == "distance":
        result.by_location.sort(key=lambda row: (row.distance_km is None, row.distance_km or 0.0))
    elif sort == "location":
        result.by_location.sort(key=lambda row: row.location_name.lower())


def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return EARTH_RADIUS_KM * c
