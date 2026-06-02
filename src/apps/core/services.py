from dataclasses import dataclass, field
from datetime import datetime, timedelta

from django.db.models import Sum
from django.urls import reverse
from django.utils import timezone

from apps.catalog.models import InventoryItem, Location, StockMovement
from apps.search import services as search_services
from apps.search.client import SearchUnavailable
from apps.search.contracts import DEFAULT_LOW_STOCK_THRESHOLD, ExpiryQuery, StockQuery

EXPIRING_WINDOW_DAYS = 30
ATTENTION_LIMIT = 8
ACTIVITY_LIMIT = 8

_MOVEMENT_ICONS = {
    StockMovement.MovementType.RECEIVED: "receive",
    StockMovement.MovementType.DISPENSED: "dispense",
    StockMovement.MovementType.TRANSFERRED: "transfer",
    StockMovement.MovementType.ADJUSTED: "adjust",
    StockMovement.MovementType.RETURNED: "return",
}


@dataclass
class Kpis:
    total_items: int
    location_count: int
    low_stock: int | None
    expiring_30d: int | None
    active_recalls: int
    recalled_units: int
    recalled_locations: int


@dataclass
class AttentionRow:
    name: str
    batch: str
    location: str
    quantity: int
    severity: str
    reason: str
    action_label: str
    action_url: str


@dataclass
class ActivityRow:
    kind: str
    summary: str
    where: str
    when: datetime


@dataclass
class DashboardSnapshot:
    kpis: Kpis
    attention: list[AttentionRow] = field(default_factory=list)
    activity: list[ActivityRow] = field(default_factory=list)
    search_ok: bool = True


def dashboard_snapshot() -> DashboardSnapshot:
    """Aggregate the operational overview shown on the home dashboard."""
    kpis, search_ok = _kpis()
    return DashboardSnapshot(
        kpis=kpis,
        attention=_attention_rows(),
        activity=_activity_rows(),
        search_ok=search_ok,
    )


def _kpis() -> tuple[Kpis, bool]:
    recalled = InventoryItem.objects.filter(status=InventoryItem.Status.RECALLED)
    recalled_units = recalled.aggregate(units=Sum("quantity"))["units"] or 0

    low_stock = None
    expiring_30d = None
    search_ok = True
    try:
        low_stock = search_services.low_stock(StockQuery()).total_items
        rollup = search_services.expiry_rollup(ExpiryQuery())
        expiring_30d = next((b.count for b in rollup.buckets if b.key == "30d"), 0)
    except SearchUnavailable:
        search_ok = False

    kpis = Kpis(
        total_items=InventoryItem.objects.count(),
        location_count=Location.objects.count(),
        low_stock=low_stock,
        expiring_30d=expiring_30d,
        active_recalls=recalled.count(),
        recalled_units=recalled_units,
        recalled_locations=recalled.values("location").distinct().count(),
    )
    return kpis, search_ok


def _attention_rows() -> list[AttentionRow]:
    today = timezone.localdate()
    horizon = today + timedelta(days=EXPIRING_WINDOW_DAYS)
    rows: list[AttentionRow] = []
    seen: set[int] = set()

    def add(item: InventoryItem, severity: str, reason: str, label: str, url_name: str) -> None:
        if item.pk in seen:
            return
        seen.add(item.pk)
        rows.append(
            AttentionRow(
                name=item.item_name,
                batch=item.batch_number,
                location=item.location.name,
                quantity=item.quantity,
                severity=severity,
                reason=reason,
                action_label=label,
                action_url=reverse(url_name),
            )
        )

    recalled = (
        InventoryItem.objects.filter(status=InventoryItem.Status.RECALLED, quantity__gt=0)
        .select_related("location")
        .order_by("-quantity")[:ATTENTION_LIMIT]
    )
    for item in recalled:
        add(item, "danger", "Recalled", "Recall lookup", "search:recall-lookup")

    expiring = (
        InventoryItem.objects.filter(
            status=InventoryItem.Status.AVAILABLE,
            quantity__gt=0,
            expiry_date__gt=today,
            expiry_date__lte=horizon,
        )
        .select_related("location")
        .order_by("expiry_date")[:ATTENTION_LIMIT]
    )
    for item in expiring:
        days = (item.expiry_date - today).days
        add(item, "warn", f"Expires in {days} days", "View expiry", "search:expiry")

    low = (
        InventoryItem.objects.filter(
            status=InventoryItem.Status.AVAILABLE,
            quantity__gt=0,
            quantity__lt=DEFAULT_LOW_STOCK_THRESHOLD,
        )
        .select_related("location")
        .order_by("quantity")[:ATTENTION_LIMIT]
    )
    for item in low:
        add(item, "warn", "Below reorder threshold", "View low stock", "search:low-stock")

    return rows[:ATTENTION_LIMIT]


def _activity_rows() -> list[ActivityRow]:
    movements = StockMovement.objects.select_related(
        "inventory_item", "performed_by", "from_location", "to_location"
    ).order_by("-created_at")[:ACTIVITY_LIMIT]
    return [
        ActivityRow(
            kind=_MOVEMENT_ICONS.get(movement.movement_type, "adjust"),
            summary=_movement_summary(movement),
            where=_movement_where(movement),
            when=movement.created_at,
        )
        for movement in movements
    ]


def _movement_summary(movement: StockMovement) -> str:
    return (
        f"{movement.get_movement_type_display()} "
        f"{movement.quantity}× {movement.inventory_item.item_name}"
    )


def _movement_where(movement: StockMovement) -> str:
    if movement.from_location and movement.to_location:
        return f"{movement.from_location.name} → {movement.to_location.name}"
    location = movement.to_location or movement.inventory_item.location
    actor = movement.performed_by.get_full_name() or movement.performed_by.get_username()
    return f"{location.name} · by {actor}"
