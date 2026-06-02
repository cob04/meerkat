from apps.search.contracts import CompositionQuery, CompositionResult, ValueBucket

BUCKET_SIZE = 50

ATC_CLASSES = {
    "A": "Alimentary tract & metabolism",
    "B": "Blood & blood-forming organs",
    "C": "Cardiovascular system",
    "D": "Dermatologicals",
    "G": "Genito-urinary & sex hormones",
    "H": "Systemic hormonal preparations",
    "J": "Anti-infectives (systemic)",
    "L": "Antineoplastic & immunomodulating",
    "M": "Musculo-skeletal system",
    "N": "Nervous system",
    "P": "Antiparasitic products",
    "R": "Respiratory system",
    "S": "Sensory organs",
    "V": "Various",
}


def _value_terms(field: str) -> dict:
    return {
        "terms": {"field": field, "size": BUCKET_SIZE},
        "aggs": {
            "value": {"sum": {"field": "line_value"}},
            "units": {"sum": {"field": "quantity"}},
        },
    }


def build_body(query: CompositionQuery) -> dict:
    return {
        "size": 0,
        "query": {"match_all": {}},
        "aggs": {
            "total_value": {"sum": {"field": "line_value"}},
            "by_manufacturer": _value_terms("drug_manufacturer.keyword"),
            "by_atc_class": _value_terms("drug_atc_class"),
            "by_dosage_form": _value_terms("drug_dosage_form"),
            "by_prescription": _value_terms("drug_requires_prescription"),
        },
    }


def parse_response(response: dict, query: CompositionQuery) -> CompositionResult:
    aggs = response.get("aggregations", {})
    total_value = float(aggs.get("total_value", {}).get("value") or 0.0)

    by_manufacturer = _buckets(aggs.get("by_manufacturer", {}))
    top = by_manufacturer[0] if by_manufacturer else None

    return CompositionResult(
        total_value=total_value,
        top_manufacturer=top.key if top else "—",
        supplier_concentration=(
            round(top.value / total_value * 100, 1) if top and total_value else 0.0
        ),
        by_manufacturer=by_manufacturer,
        by_atc_class=_buckets(aggs.get("by_atc_class", {}), labels=ATC_CLASSES),
        by_dosage_form=_buckets(aggs.get("by_dosage_form", {}), titleize=True),
        by_prescription=_buckets(aggs.get("by_prescription", {}), prescription=True),
        engine_took_ms=response.get("took", 0),
    )


def _label(key, labels, titleize, prescription):
    if prescription:
        return "Prescription required" if key in (True, "true", 1, "1") else "Over the counter"
    if labels:
        return labels.get(str(key), str(key))
    if titleize:
        return str(key).replace("_", " ").title()
    return str(key)


def _buckets(agg, labels=None, titleize=False, prescription=False) -> list[ValueBucket]:
    out = []
    for b in agg.get("buckets", []):
        key = b.get("key")
        if key in (None, ""):
            continue
        out.append(
            ValueBucket(
                key=_label(key, labels, titleize, prescription),
                value=float(b.get("value", {}).get("value") or 0.0),
                quantity=int(b.get("units", {}).get("value") or 0),
                items=int(b.get("doc_count", 0)),
            )
        )
    return out
