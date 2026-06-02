from apps.search.contracts import (
    COVERAGE_PRODUCT_LIMIT,
    SINGLE_SOURCE_TOP_N,
    CoverageBand,
    CoverageQuery,
    CoverageResult,
    SingleSourceProduct,
)


def build_body(query: CoverageQuery) -> dict:
    return {
        "size": 0,
        "query": {
            "bool": {
                "filter": [
                    {"term": {"status": "available"}},
                    {"range": {"quantity": {"gt": 0}}},
                ]
            }
        },
        "aggs": {
            "products": {
                "terms": {"field": "product_name.keyword", "size": COVERAGE_PRODUCT_LIMIT},
                "aggs": {
                    "site_count": {"cardinality": {"field": "location_id"}},
                    "units": {"sum": {"field": "quantity"}},
                    "value": {"sum": {"field": "line_value"}},
                    "top_site": {"terms": {"field": "location_name.keyword", "size": 1}},
                },
            }
        },
    }


def parse_response(response: dict, query: CoverageQuery) -> CoverageResult:
    buckets = response.get("aggregations", {}).get("products", {}).get("buckets", [])

    one = two = three_plus = 0
    single_source: list[SingleSourceProduct] = []

    for b in buckets:
        sites = int(b.get("site_count", {}).get("value") or 0)
        if sites <= 1:
            one += 1
            site_buckets = b.get("top_site", {}).get("buckets", [])
            single_source.append(
                SingleSourceProduct(
                    product=str(b.get("key", "")),
                    site=str(site_buckets[0]["key"]) if site_buckets else "—",
                    units=int(b.get("units", {}).get("value") or 0),
                    value=float(b.get("value", {}).get("value") or 0.0),
                )
            )
        elif sites == 2:
            two += 1
        else:
            three_plus += 1

    single_source.sort(key=lambda s: s.value, reverse=True)

    return CoverageResult(
        products_in_stock=len(buckets),
        single_source_count=one,
        well_covered_count=three_plus,
        coverage_bands=[
            CoverageBand(label="1 site", products=one),
            CoverageBand(label="2 sites", products=two),
            CoverageBand(label="3+ sites", products=three_plus),
        ],
        single_source=single_source[:SINGLE_SOURCE_TOP_N],
        engine_took_ms=response.get("took", 0),
    )
