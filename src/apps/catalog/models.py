from django.conf import settings
from django.db import models

from apps.core.models import AuditModel


class Product(AuditModel):
    name = models.CharField(max_length=255)
    sku = models.CharField(max_length=100, unique=True, verbose_name="SKU")
    category = models.CharField(max_length=100, blank=True)
    description = models.TextField(blank=True)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name

    @property
    def is_drug(self) -> bool:
        return hasattr(self, "drug")


class Drug(AuditModel):
    class DosageForm(models.TextChoices):
        TABLET = "tablet", "Tablet"
        CAPSULE = "capsule", "Capsule"
        LIQUID = "liquid", "Liquid"
        INJECTION = "injection", "Injection"
        CREAM = "cream", "Cream"
        OINTMENT = "ointment", "Ointment"
        INHALER = "inhaler", "Inhaler"
        DROPS = "drops", "Drops"
        SUPPOSITORY = "suppository", "Suppository"
        PATCH = "patch", "Patch"

    class StorageCondition(models.TextChoices):
        ROOM_TEMPERATURE = "room_temperature", "Room Temperature"
        REFRIGERATED = "refrigerated", "Refrigerated (2-8C)"
        FROZEN = "frozen", "Frozen"
        CONTROLLED_ROOM = "controlled_room", "Controlled Room Temperature"

    product = models.OneToOneField(Product, on_delete=models.CASCADE, related_name="drug")
    inn_name = models.CharField(max_length=255, verbose_name="INN name")
    brand_name = models.CharField(max_length=255, blank=True)
    atc_code = models.CharField(max_length=7, db_index=True, verbose_name="ATC code")
    dosage_form = models.CharField(max_length=20, choices=DosageForm.choices)
    strength = models.CharField(max_length=50)
    unit = models.CharField(max_length=20)
    manufacturer = models.CharField(max_length=255, blank=True)
    requires_prescription = models.BooleanField(default=False)
    schedule = models.CharField(max_length=5, blank=True)
    storage_condition = models.CharField(
        max_length=20,
        choices=StorageCondition.choices,
        default=StorageCondition.ROOM_TEMPERATURE,
    )
    age_restricted = models.BooleanField(default=False)

    class Meta:
        ordering = ["inn_name"]

    def __str__(self) -> str:
        return f"{self.inn_name} {self.strength}{self.unit}"


class Location(AuditModel):
    class LocationType(models.TextChoices):
        WAREHOUSE = "warehouse", "Warehouse"
        PHARMACY = "pharmacy", "Pharmacy"
        WARD = "ward", "Ward"

    name = models.CharField(max_length=255)
    location_type = models.CharField(max_length=20, choices=LocationType.choices)
    address = models.TextField(blank=True)
    parent_location = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="children",
    )

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return f"{self.name} ({self.get_location_type_display()})"


class InventoryItem(AuditModel):
    class Status(models.TextChoices):
        AVAILABLE = "available", "Available"
        RESERVED = "reserved", "Reserved"
        EXPIRED = "expired", "Expired"
        RECALLED = "recalled", "Recalled"

    item_name = models.CharField(max_length=255)
    product = models.ForeignKey(
        Product,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="inventory_items",
    )
    location = models.ForeignKey(Location, on_delete=models.PROTECT, related_name="inventory_items")
    batch_number = models.CharField(max_length=100)
    quantity = models.PositiveIntegerField()
    expiry_date = models.DateField()
    unit_cost = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.AVAILABLE)

    class Meta:
        ordering = ["expiry_date"]

    def __str__(self) -> str:
        return f"{self.item_name} - {self.batch_number} @ {self.location.name}"

    @property
    def is_cataloged(self) -> bool:
        return self.product_id is not None


class StockMovement(AuditModel):
    class MovementType(models.TextChoices):
        RECEIVED = "received", "Received"
        DISPENSED = "dispensed", "Dispensed"
        TRANSFERRED = "transferred", "Transferred"
        ADJUSTED = "adjusted", "Adjusted"
        RETURNED = "returned", "Returned"

    inventory_item = models.ForeignKey(
        InventoryItem, on_delete=models.PROTECT, related_name="movements"
    )
    movement_type = models.CharField(max_length=20, choices=MovementType.choices)
    quantity = models.IntegerField()
    from_location = models.ForeignKey(
        Location,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="outgoing_movements",
    )
    to_location = models.ForeignKey(
        Location,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="incoming_movements",
    )
    performed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="stock_movements",
    )
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.get_movement_type_display()} - {self.inventory_item} ({self.quantity})"
