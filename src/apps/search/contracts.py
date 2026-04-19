from dataclasses import dataclass, field
from typing import Any

DEFAULT_PAGE_SIZE = 25


@dataclass
class InventoryQuery:
    q: str | None = None
    page: int = 1
    page_size: int = DEFAULT_PAGE_SIZE
    sort: str = "_score"


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
