import logging
from dataclasses import dataclass

from apps.catalog.models import Drug, InventoryItem, Location, Product, StockMovement
from apps.cdc.opensearch_client import INVENTORY_INDEX, MOVEMENTS_INDEX

logger = logging.getLogger(__name__)

TOPIC_INVENTORY = "meerkat.public.catalog_inventoryitem"
TOPIC_PRODUCT = "meerkat.public.catalog_product"
TOPIC_DRUG = "meerkat.public.catalog_drug"
TOPIC_LOCATION = "meerkat.public.catalog_location"
TOPIC_MOVEMENT = "meerkat.public.catalog_stockmovement"


@dataclass
class IndexAction:
    doc_id: int
    document: dict
    index: str = INVENTORY_INDEX


@dataclass
class DeleteAction:
    doc_id: int
    index: str = INVENTORY_INDEX


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
    elif topic == TOPIC_MOVEMENT:
        return _handle_movement(op, after, before)

    logger.warning("Unknown topic: %s", topic)
    return []


def _handle_movement(
    op: str, after: dict | None, before: dict | None
) -> list[IndexAction | DeleteAction]:
    if op in ("c", "r", "u"):
        if after is None:
            return []
        if after.get("deleted_at") is not None:
            return [DeleteAction(doc_id=after["id"], index=MOVEMENTS_INDEX)]
        doc = _build_movement_doc(after["id"])
        return [doc] if doc else []
    elif op == "d":
        if before and "id" in before:
            return [DeleteAction(doc_id=before["id"], index=MOVEMENTS_INDEX)]
    return []


def _build_movement_doc(movement_id: int) -> IndexAction | None:
    try:
        movement = StockMovement.objects.select_related(
            "inventory_item__product", "from_location", "to_location", "performed_by"
        ).get(pk=movement_id)
    except StockMovement.DoesNotExist:
        logger.warning("StockMovement %s not found", movement_id)
        return None

    item = movement.inventory_item
    location = movement.to_location or movement.from_location or item.location
    doc = {
        "movement_type": movement.movement_type,
        "quantity": movement.quantity,
        "item_name": item.item_name,
        "product_name": item.product.name if item.product else None,
        "product_category": item.product.category if item.product else None,
        "location_name": location.name if location else None,
        "performed_by": movement.performed_by.get_username(),
        "created_at": movement.created_at.isoformat() if movement.created_at else None,
    }
    return IndexAction(doc_id=movement.pk, document=doc, index=MOVEMENTS_INDEX)


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
                    "drug_atc_class": drug.atc_code[0] if drug.atc_code else None,
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
