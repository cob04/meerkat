from django.shortcuts import render

from apps.search import services
from apps.search.client import SearchUnavailable
from apps.search.contracts import DEFAULT_PAGE_SIZE, InventoryQuery


def _render(request, full_template: str, partial_template: str, context: dict):
    template = partial_template if request.headers.get("HX-Request") else full_template
    return render(request, template, context)


def catalog_search(request):
    query = InventoryQuery(
        q=request.GET.get("q") or None,
        page=_int_param(request.GET.get("page"), default=1, minimum=1),
        page_size=_int_param(request.GET.get("page_size"), default=DEFAULT_PAGE_SIZE, minimum=1),
        sort=request.GET.get("sort") or "_score",
        status=request.GET.getlist("status"),
        location=request.GET.getlist("location"),
        category=request.GET.getlist("category"),
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


def _int_param(raw: str | None, default: int, minimum: int) -> int:
    try:
        value = int(raw) if raw is not None else default
    except (TypeError, ValueError):
        value = default
    return max(value, minimum)
