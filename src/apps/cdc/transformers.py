import logging
from dataclasses import dataclass

from apps.catalog.models import Drug, InventoryItem, Location, Product

logger = logging.getLogger(__name__)

TOPIC_INVENTORY = "meerkat.public.catalog_inventoryitem"
TOPIC_PRODUCT = "meerkat.public.catalog_product"
TOPIC_DRUG = "meerkat.public.catalog_drug"
TOPIC_LOCATION = "meerkat.public.catalog_location"


@dataclass
class IndexAction:
    doc_id: int
    document: dict


@dataclass
class DeleteAction:
    doc_id: int


def transform(topic: str, event: dict) -> list[IndexAction | DeleteAction]:
    op = event.get("op")
    after = event.get("after")
    before = event.get("before")

    if topic == TOPIC_INVENTORY:
        return _handle_inventory_item(op, after, before)
    elif topic in (TOPIC_PRODUCT, TOPIC_DRUG):
        return _handle_product_or_drug(op, after, before)
    elif topic == TOPIC_LOCATION:
        return _handle_location(op, after, before)

    logger.warning("Unknown topic: %s", topic)
    return []


def _handle_inventory_item(
    op: str, after: dict | None, before: dict | None
) -> list[IndexAction | DeleteAction]:
    if op in ("c", "r", "u"):
        if after is None:
            return []
        if after.get("deleted_at") is not None:
            return [DeleteAction(doc_id=after["id"])]
        return [_build_inventory_doc(after["id"])]
    elif op == "d":
        if before and "id" in before:
            return [DeleteAction(doc_id=before["id"])]
    return []


def _handle_product_or_drug(
    op: str, after: dict | None, before: dict | None
) -> list[IndexAction | DeleteAction]:
    if op in ("c", "r", "u"):
        record = after
    elif op == "d":
        record = before
    else:
        return []

    if record is None:
        return []

    product_id = record.get("id") if "sku" in record else record.get("product_id")
    if product_id is None:
        return []

    return _reindex_items_for_product(product_id)


def _handle_location(
    op: str, after: dict | None, before: dict | None
) -> list[IndexAction | DeleteAction]:
    if op in ("c", "r", "u"):
        record = after
    elif op == "d":
        record = before
    else:
        return []

    if record is None:
        return []

    location_id = record.get("id")
    if location_id is None:
        return []

    return _reindex_items_for_location(location_id)


def _build_inventory_doc(item_id: int) -> IndexAction | None:
    try:
        item = InventoryItem.objects.select_related("product__drug", "location").get(pk=item_id)
    except InventoryItem.DoesNotExist:
        logger.warning("InventoryItem %s not found", item_id)
        return None

    doc = {
        "item_name": item.item_name,
        "batch_number": item.batch_number,
        "quantity": item.quantity,
        "expiry_date": item.expiry_date.isoformat() if item.expiry_date else None,
        "unit_cost": float(item.unit_cost),
        "line_value": float(item.unit_cost) * item.quantity,
        "status": item.status,
        "location_id": item.location_id,
        "location_name": item.location.name,
        "location_type": item.location.location_type,
        "created_at": item.created_at.isoformat() if item.created_at else None,
        "updated_at": item.updated_at.isoformat() if item.updated_at else None,
    }

    if item.location.has_coordinates:
        doc["location_geo"] = {
            "lat": float(item.location.latitude),
            "lon": float(item.location.longitude),
        }

    if item.product:
        doc.update(
            {
                "product_id": item.product_id,
                "product_name": item.product.name,
                "product_sku": item.product.sku,
                "product_category": item.product.category,
                "is_drug": item.product.is_drug,
            }
        )
        if hasattr(item.product, "drug"):
            drug = item.product.drug
            doc.update(
                {
                    "drug_id": drug.pk,
                    "drug_inn_name": drug.inn_name,
                    "drug_brand_name": drug.brand_name,
                    "drug_atc_code": drug.atc_code,
                    "drug_dosage_form": drug.dosage_form,
                    "drug_strength": f"{drug.strength}{drug.unit}",
                    "drug_manufacturer": drug.manufacturer,
                    "drug_requires_prescription": drug.requires_prescription,
                    "drug_storage_condition": drug.storage_condition,
                }
            )

    return IndexAction(doc_id=item.pk, document=doc)


def _reindex_items_for_product(product_id: int) -> list[IndexAction]:
    item_ids = list(
        InventoryItem.objects.filter(product_id=product_id).values_list("id", flat=True)
    )
    actions = []
    for item_id in item_ids:
        action = _build_inventory_doc(item_id)
        if action:
            actions.append(action)
    return actions


def _reindex_items_for_location(location_id: int) -> list[IndexAction]:
    item_ids = list(
        InventoryItem.objects.filter(location_id=location_id).values_list("id", flat=True)
    )
    actions = []
    for item_id in item_ids:
        action = _build_inventory_doc(item_id)
        if action:
            actions.append(action)
    return actions
