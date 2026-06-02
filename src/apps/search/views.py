from django.shortcuts import render

from apps.search import services
from apps.search.client import SearchUnavailable
from apps.search.contracts import (
    AVAILABILITY_SORTS,
    DEFAULT_LOW_STOCK_THRESHOLD,
    DEFAULT_PAGE_SIZE,
    AvailabilityQuery,
    CoverageQuery,
    ExpiryQuery,
    InventoryQuery,
    RecallQuery,
    StockQuery,
    ValueAtRiskQuery,
    ValueQuery,
)


def _render(request, full_template: str, partial_template: str, context: dict):
    is_partial = request.headers.get("HX-Request") and not request.headers.get("HX-Boosted")
    template = partial_template if is_partial else full_template
    return render(request, template, context)


def inventory_value(request):
    try:
        result = services.inventory_value(ValueQuery())
    except SearchUnavailable:
        result = None
    return render(request, "search/value.html", {"result": result})


def value_at_risk(request):
    try:
        result = services.value_at_risk(ValueAtRiskQuery())
    except SearchUnavailable:
        result = None
    return render(request, "search/value_at_risk.html", {"result": result})


def network_coverage(request):
    try:
        result = services.network_coverage(CoverageQuery())
    except SearchUnavailable:
        result = None
    return render(request, "search/coverage.html", {"result": result})


def catalog_search(request):
    if "suggest" in request.GET:
        suggestions = services.suggest(request.GET.get("q"))
        return render(request, "_suggestions.html", {"suggestions": suggestions})

    query = InventoryQuery(
        q=request.GET.get("q") or None,
        page=_int_param(request.GET.get("page"), default=1, minimum=1),
        page_size=_int_param(request.GET.get("page_size"), default=DEFAULT_PAGE_SIZE, minimum=1),
        sort=request.GET.get("sort") or "_score",
        status=request.GET.getlist("status"),
        location=request.GET.getlist("location"),
        category=request.GET.getlist("category"),
        expiry_bucket=request.GET.get("expiry_bucket") or None,
    )

    base_params = request.GET.copy()
    base_params.pop("page", None)
    base_qs = base_params.urlencode()

    try:
        results = services.search_inventory(query)
    except SearchUnavailable:
        return _render(
            request,
            "search/catalog_search.html",
            "search/_unavailable.html",
            {"query": query},
        )

    return _render(
        request,
        "search/catalog_search.html",
        "search/_results.html",
        {"query": query, "results": results, "base_qs": base_qs},
    )


def availability(request):
    product_id = _optional_int(request.GET.get("product_id"))
    drug_id = _optional_int(request.GET.get("drug_id"))
    if product_id is None and drug_id is None:
        return _render(
            request,
            "search/availability.html",
            "search/_availability.html",
            {"error": "missing-target"},
        )

    sort = request.GET.get("sort") or None
    if sort and sort not in AVAILABILITY_SORTS:
        sort = None

    query = AvailabilityQuery(
        product_id=product_id,
        drug_id=drug_id,
        from_location_id=_optional_int(request.GET.get("from_location_id")),
        max_distance_km=_optional_int(request.GET.get("max_distance_km")),
        sort=sort,
    )

    try:
        result = services.availability(query)
    except SearchUnavailable:
        return _render(
            request,
            "search/availability.html",
            "search/_unavailable.html",
            {"query": query},
        )

    return _render(
        request,
        "search/availability.html",
        "search/_availability.html",
        {"query": query, "result": result},
    )


def expiry(request):
    query = ExpiryQuery(
        location=request.GET.getlist("location"),
        category=request.GET.getlist("category"),
    )

    try:
        rollup = services.expiry_rollup(query)
    except SearchUnavailable:
        return _render(
            request,
            "search/expiry.html",
            "search/_unavailable.html",
            {"query": query},
        )

    return _render(
        request,
        "search/expiry.html",
        "search/_expiry.html",
        {"query": query, "rollup": rollup},
    )


def low_stock(request):
    query = StockQuery(
        threshold=_int_param(
            request.GET.get("threshold"), default=DEFAULT_LOW_STOCK_THRESHOLD, minimum=1
        ),
        location=request.GET.getlist("location"),
        category=request.GET.getlist("category"),
    )

    try:
        result = services.low_stock(query)
    except SearchUnavailable:
        return _render(
            request,
            "search/stock.html",
            "search/_unavailable.html",
            {"query": query},
        )

    return _render(
        request,
        "search/stock.html",
        "search/_stock.html",
        {"query": query, "result": result},
    )


def recall_lookup(request):
    query = RecallQuery(
        manufacturer=(request.GET.get("manufacturer") or "").strip() or None,
        batch_pattern=(request.GET.get("batch_pattern") or "").strip() or None,
        drug_id=_optional_int(request.GET.get("drug_id")),
        created_from=(request.GET.get("created_from") or "").strip() or None,
        created_to=(request.GET.get("created_to") or "").strip() or None,
    )

    if not query.has_criteria:
        return _render(
            request,
            "search/recall.html",
            "search/_recall.html",
            {"query": query, "result": None},
        )

    try:
        result = services.recall_impact(query)
    except SearchUnavailable:
        return _render(
            request,
            "search/recall.html",
            "search/_unavailable.html",
            {"query": query},
        )

    return _render(
        request,
        "search/recall.html",
        "search/_recall.html",
        {"query": query, "result": result},
    )


def _int_param(raw: str | None, default: int, minimum: int) -> int:
    try:
        value = int(raw) if raw is not None else default
    except (TypeError, ValueError):
        value = default
    return max(value, minimum)


def _optional_int(raw: str | None) -> int | None:
    if raw in (None, ""):
        return None
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return None
    return value if value > 0 else None
