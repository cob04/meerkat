from dataclasses import dataclass

from django.contrib.auth import get_user_model
from django.db.models import Count, Q

from apps.catalog.models import Drug, InventoryItem, Location, Product, StockMovement
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


@dataclass
class FacetOption:
    value: str
    label: str
    count: int
    selected: bool


@dataclass
class FacetGroup:
    param: str
    label: str
    options: list[FacetOption]


@dataclass
class SearchResults:
    items: list
    total: int
    facets: list[FacetGroup]


def _terms_facet(base_qs, field, param, label, selected, labels=None):
    options = []
    for row in base_qs.values(field).annotate(count=Count("id")).order_by("-count", field):
        value = row[field]
        if value in (None, ""):
            continue
        options.append(
            FacetOption(
                value=str(value),
                label=str(labels.get(value, value)) if labels else str(value),
                count=row["count"],
                selected=str(value) in selected,
            )
        )
    return FacetGroup(param=param, label=label, options=options)


def _choice_facet(base_qs, param, label, selected, specs):
    options = [
        FacetOption(
            value=value, label=lbl, count=base_qs.filter(cond).count(), selected=value in selected
        )
        for value, lbl, cond in specs
    ]
    return FacetGroup(param=param, label=label, options=options)


def search_products(
    q=None,
    categories=None,
    types=None,
    dosage_forms=None,
    prescription=None,
    active=None,
) -> SearchResults:
    """Filter the product catalog by text and facets, with counts over the text match."""
    categories = categories or []
    types = types or []
    dosage_forms = dosage_forms or []
    prescription = prescription or []
    active = active or []

    base = Product.objects.select_related("drug")
    if q:
        base = base.filter(Q(name__icontains=q) | Q(sku__icontains=q))

    items = base
    if categories:
        items = items.filter(category__in=categories)
    if types:
        type_cond = Q()
        if "drug" in types:
            type_cond |= Q(drug__isnull=False)
        if "non_drug" in types:
            type_cond |= Q(drug__isnull=True)
        items = items.filter(type_cond)
    if dosage_forms:
        items = items.filter(drug__dosage_form__in=dosage_forms)
    if prescription:
        presc_cond = Q()
        if "yes" in prescription:
            presc_cond |= Q(drug__requires_prescription=True)
        if "no" in prescription:
            presc_cond |= Q(drug__requires_prescription=False)
        items = items.filter(presc_cond)
    if active:
        active_cond = Q()
        if "yes" in active:
            active_cond |= Q(is_active=True)
        if "no" in active:
            active_cond |= Q(is_active=False)
        items = items.filter(active_cond)

    ordered = list(items.order_by("name"))
    facets = [
        _terms_facet(base, "category", "category", "Category", categories),
        _choice_facet(
            base,
            "type",
            "Type",
            types,
            [
                ("drug", "Drug", Q(drug__isnull=False)),
                ("non_drug", "Non-drug", Q(drug__isnull=True)),
            ],
        ),
        _terms_facet(
            base,
            "drug__dosage_form",
            "dosage_form",
            "Dosage form",
            dosage_forms,
            labels=dict(Drug.DosageForm.choices),
        ),
        _choice_facet(
            base,
            "prescription",
            "Prescription",
            prescription,
            [
                ("yes", "Required", Q(drug__requires_prescription=True)),
                ("no", "Not required", Q(drug__requires_prescription=False)),
            ],
        ),
        _choice_facet(
            base,
            "active",
            "Status",
            active,
            [
                ("yes", "Active", Q(is_active=True)),
                ("no", "Inactive", Q(is_active=False)),
            ],
        ),
    ]
    return SearchResults(items=ordered, total=len(ordered), facets=facets)


def search_locations(q=None, types=None, gps=None) -> SearchResults:
    """Filter locations by text and facets, with counts over the text match."""
    types = types or []
    gps = gps or []

    base = Location.objects.all()
    if q:
        base = base.filter(Q(name__icontains=q) | Q(address__icontains=q))

    items = base
    if types:
        items = items.filter(location_type__in=types)
    if gps:
        gps_cond = Q()
        if "yes" in gps:
            gps_cond |= Q(latitude__isnull=False, longitude__isnull=False)
        if "no" in gps:
            gps_cond |= Q(latitude__isnull=True) | Q(longitude__isnull=True)
        items = items.filter(gps_cond)

    ordered = list(items.order_by("name"))
    facets = [
        _terms_facet(
            base,
            "location_type",
            "type",
            "Type",
            types,
            labels=dict(Location.LocationType.choices),
        ),
        _choice_facet(
            base,
            "gps",
            "GPS",
            gps,
            [
                ("yes", "Has coordinates", Q(latitude__isnull=False, longitude__isnull=False)),
                ("no", "No coordinates", Q(latitude__isnull=True) | Q(longitude__isnull=True)),
            ],
        ),
    ]
    return SearchResults(items=ordered, total=len(ordered), facets=facets)


def _suggest(queryset, field, q, limit=8):
    q = (q or "").strip()
    if not q:
        return []
    values = queryset.values_list(field, flat=True).distinct().order_by(field)[: limit * 4]
    return list(dict.fromkeys(values))[:limit]


def suggest_inventory(q, limit=8) -> list[str]:
    """Distinct inventory item names matching a partial query, for autocomplete."""
    if not (q or "").strip():
        return []
    base = InventoryItem.objects.filter(Q(item_name__icontains=q) | Q(product__name__icontains=q))
    return _suggest(base, "item_name", q, limit)


def suggest_products(q, limit=8) -> list[str]:
    """Distinct product names matching a partial query, for autocomplete."""
    if not (q or "").strip():
        return []
    base = Product.objects.filter(Q(name__icontains=q) | Q(sku__icontains=q))
    return _suggest(base, "name", q, limit)


def suggest_locations(q, limit=8) -> list[str]:
    """Distinct location names matching a partial query, for autocomplete."""
    if not (q or "").strip():
        return []
    base = Location.objects.filter(Q(name__icontains=q) | Q(address__icontains=q))
    return _suggest(base, "name", q, limit)
