from dataclasses import dataclass, field
from typing import Any

DEFAULT_PAGE_SIZE = 25


@dataclass
class InventoryQuery:
    q: str | None = None
    page: int = 1
    page_size: int = DEFAULT_PAGE_SIZE
    sort: str = "_score"
    status: list[str] = field(default_factory=list)
    location: list[str] = field(default_factory=list)
    category: list[str] = field(default_factory=list)

    @property
    def has_filters(self) -> bool:
        return bool(self.status or self.location or self.category)


@dataclass
class InventoryDoc:
    id: int
    item_name: str
    product_name: str | None
    batch_number: str
    location_name: str | None
    quantity: int
    status: str
    expiry_date: str | None
    score: float | None = None

    @classmethod
    def from_hit(cls, hit: dict[str, Any]) -> "InventoryDoc":
        source = hit.get("_source", {})
        return cls(
            id=int(hit["_id"]),
            item_name=source.get("item_name", ""),
            product_name=source.get("product_name"),
            batch_number=source.get("batch_number", ""),
            location_name=source.get("location_name"),
            quantity=source.get("quantity", 0),
            status=source.get("status", ""),
            expiry_date=source.get("expiry_date"),
            score=hit.get("_score"),
        )


@dataclass
class FacetBreakdown:
    status: dict[str, int] = field(default_factory=dict)
    location: dict[str, int] = field(default_factory=dict)
    category: dict[str, int] = field(default_factory=dict)


@dataclass
class InventoryResults:
    items: list[InventoryDoc]
    total: int
    page: int
    page_size: int
    engine_took_ms: int
    facets: FacetBreakdown | None = None

    @property
    def total_pages(self) -> int:
        if self.page_size <= 0:
            return 0
        return (self.total + self.page_size - 1) // self.page_size

    @property
    def has_next(self) -> bool:
        return self.page < self.total_pages

    @property
    def has_prev(self) -> bool:
        return self.page > 1


AVAILABILITY_SORTS = ("distance", "-quantity", "location")
DEFAULT_AVAILABILITY_SORT_WITH_ORIGIN = "distance"
DEFAULT_AVAILABILITY_SORT_WITHOUT_ORIGIN = "-quantity"


@dataclass
class AvailabilityQuery:
    product_id: int | None = None
    drug_id: int | None = None
    from_location_id: int | None = None
    max_distance_km: int | None = None
    sort: str | None = None

    def __post_init__(self):
        if self.product_id is None and self.drug_id is None:
            raise ValueError("AvailabilityQuery requires product_id or drug_id")
        if self.sort is None:
            self.sort = (
                DEFAULT_AVAILABILITY_SORT_WITH_ORIGIN
                if self.from_location_id
                else DEFAULT_AVAILABILITY_SORT_WITHOUT_ORIGIN
            )
        if self.sort not in AVAILABILITY_SORTS:
            raise ValueError(f"Unsupported sort: {self.sort}")


@dataclass
class LocationStock:
    location_id: int
    location_name: str
    quantity: int
    item_count: int
    distance_km: float | None = None


@dataclass
class AvailabilityResult:
    product_id: int | None
    drug_id: int | None
    total_quantity: int
    total_items: int
    by_location: list[LocationStock]
    engine_took_ms: int
    origin_resolved: bool = False
