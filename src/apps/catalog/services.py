from django.contrib.auth import get_user_model

from apps.catalog.models import InventoryItem, Location, Product, StockMovement
from apps.core.models import AuditEvent

User = get_user_model()


def _log_event(user, action: str, item: InventoryItem, description: str, metadata: dict = None):
    AuditEvent(
        user=user,
        action=action,
        model_name="InventoryItem",
        record_id=item.pk,
        description=description,
        metadata=metadata or {},
    ).save()


def receive_stock(
    item_name: str,
    location: Location,
    batch_number: str,
    quantity: int,
    expiry_date,
    unit_cost,
    user: User,
    product: Product = None,
    notes: str = "",
) -> InventoryItem:
    item = InventoryItem(
        item_name=item_name,
        product=product,
        location=location,
        batch_number=batch_number,
        quantity=quantity,
        expiry_date=expiry_date,
        unit_cost=unit_cost,
    )
    item.save()

    StockMovement(
        inventory_item=item,
        movement_type=StockMovement.MovementType.RECEIVED,
        quantity=quantity,
        to_location=location,
        performed_by=user,
        notes=notes,
    ).save()

    _log_event(
        user=user,
        action="receive",
        item=item,
        description=f"Received {quantity}x {item_name} ({batch_number}) at {location.name}",
        metadata={"quantity": quantity, "batch": batch_number, "location_id": location.pk},
    )

    return item


def dispense_stock(
    item: InventoryItem,
    quantity: int,
    user: User,
    notes: str = "",
) -> StockMovement:
    if item.status != InventoryItem.Status.AVAILABLE:
        raise ValueError(f"Cannot dispense item with status '{item.status}'.")
    if quantity <= 0:
        raise ValueError("Quantity must be positive.")
    if quantity > item.quantity:
        raise ValueError(f"Insufficient stock. Available: {item.quantity}, requested: {quantity}.")

    item.quantity -= quantity
    item.save(update_fields=["quantity", "updated_at"])

    movement = StockMovement(
        inventory_item=item,
        movement_type=StockMovement.MovementType.DISPENSED,
        quantity=quantity,
        from_location=item.location,
        performed_by=user,
        notes=notes,
    )
    movement.save()

    _log_event(
        user=user,
        action="dispense",
        item=item,
        description=f"Dispensed {quantity}x {item.item_name} ({item.batch_number}) from {item.location.name}",
        metadata={
            "quantity": quantity,
            "batch": item.batch_number,
            "remaining": item.quantity,
            "location_id": item.location_id,
        },
    )

    return movement


def transfer_stock(
    item: InventoryItem,
    to_location: Location,
    quantity: int,
    user: User,
    notes: str = "",
) -> StockMovement:
    if item.status != InventoryItem.Status.AVAILABLE:
        raise ValueError(f"Cannot transfer item with status '{item.status}'.")
    if quantity <= 0:
        raise ValueError("Quantity must be positive.")
    if quantity > item.quantity:
        raise ValueError(f"Insufficient stock. Available: {item.quantity}, requested: {quantity}.")
    if to_location.pk == item.location_id:
        raise ValueError("Source and destination locations are the same.")

    from_location = item.location

    item.quantity -= quantity
    item.save(update_fields=["quantity", "updated_at"])

    dest_item = InventoryItem(
        item_name=item.item_name,
        product=item.product,
        location=to_location,
        batch_number=item.batch_number,
        quantity=quantity,
        expiry_date=item.expiry_date,
        unit_cost=item.unit_cost,
        status=item.status,
    )
    dest_item.save()

    movement = StockMovement(
        inventory_item=item,
        movement_type=StockMovement.MovementType.TRANSFERRED,
        quantity=quantity,
        from_location=from_location,
        to_location=to_location,
        performed_by=user,
        notes=notes,
    )
    movement.save()

    _log_event(
        user=user,
        action="transfer",
        item=item,
        description=f"Transferred {quantity}x {item.item_name} ({item.batch_number}) from {from_location.name} to {to_location.name}",
        metadata={
            "quantity": quantity,
            "from_location_id": from_location.pk,
            "to_location_id": to_location.pk,
            "dest_item_id": dest_item.pk,
            "remaining_at_source": item.quantity,
        },
    )

    return movement


def adjust_stock(
    item: InventoryItem,
    new_quantity: int,
    reason: str,
    user: User,
) -> StockMovement:
    if not reason.strip():
        raise ValueError("Reason is required for stock adjustments.")
    if new_quantity < 0:
        raise ValueError("Quantity cannot be negative.")

    old_quantity = item.quantity
    difference = new_quantity - old_quantity

    item.quantity = new_quantity
    item.save(update_fields=["quantity", "updated_at"])

    movement = StockMovement(
        inventory_item=item,
        movement_type=StockMovement.MovementType.ADJUSTED,
        quantity=difference,
        from_location=item.location,
        to_location=item.location,
        performed_by=user,
        notes=reason,
    )
    movement.save()

    _log_event(
        user=user,
        action="adjust",
        item=item,
        description=f"Adjusted {item.item_name} ({item.batch_number}) at {item.location.name}: {old_quantity} -> {new_quantity}",
        metadata={
            "old_quantity": old_quantity,
            "new_quantity": new_quantity,
            "difference": difference,
            "reason": reason,
        },
    )

    return movement


def recall_batch(
    batch_number: str,
    reason: str,
    user: User,
) -> list[InventoryItem]:
    items = list(
        InventoryItem.objects.filter(
            batch_number=batch_number,
            status=InventoryItem.Status.AVAILABLE,
        ).select_related("location")
    )

    if not items:
        raise ValueError(f"No available inventory found for batch '{batch_number}'.")

    for item in items:
        old_status = item.status
        item.status = InventoryItem.Status.RECALLED
        item.save(update_fields=["status", "updated_at"])

        StockMovement(
            inventory_item=item,
            movement_type=StockMovement.MovementType.ADJUSTED,
            quantity=0,
            from_location=item.location,
            performed_by=user,
            notes=f"Recall: {reason}",
        ).save()

        _log_event(
            user=user,
            action="recall",
            item=item,
            description=f"Recalled {item.item_name} ({batch_number}) at {item.location.name} - {item.quantity} units",
            metadata={
                "batch": batch_number,
                "quantity_affected": item.quantity,
                "location_id": item.location_id,
                "old_status": old_status,
                "reason": reason,
            },
        )

    return items


def return_stock(
    item: InventoryItem,
    quantity: int,
    user: User,
    notes: str = "",
) -> StockMovement:
    if quantity <= 0:
        raise ValueError("Quantity must be positive.")

    item.quantity += quantity
    if item.status == InventoryItem.Status.EXPIRED:
        raise ValueError("Cannot return expired stock.")
    item.save(update_fields=["quantity", "updated_at"])

    movement = StockMovement(
        inventory_item=item,
        movement_type=StockMovement.MovementType.RETURNED,
        quantity=quantity,
        to_location=item.location,
        performed_by=user,
        notes=notes,
    )
    movement.save()

    _log_event(
        user=user,
        action="return",
        item=item,
        description=f"Returned {quantity}x {item.item_name} ({item.batch_number}) to {item.location.name}",
        metadata={
            "quantity": quantity,
            "batch": item.batch_number,
            "new_total": item.quantity,
            "location_id": item.location_id,
        },
    )

    return movement
