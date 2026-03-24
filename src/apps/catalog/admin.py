from django.contrib import admin

from apps.catalog.models import Drug, InventoryItem, Location, Product, StockMovement


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ["name", "sku", "category", "unit_price", "is_active"]
    list_filter = ["is_active", "category"]
    search_fields = ["name", "sku"]


@admin.register(Drug)
class DrugAdmin(admin.ModelAdmin):
    list_display = [
        "inn_name",
        "brand_name",
        "atc_code",
        "dosage_form",
        "strength",
        "requires_prescription",
    ]
    list_filter = ["dosage_form", "requires_prescription", "schedule", "storage_condition"]
    search_fields = ["inn_name", "brand_name", "atc_code"]


@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    list_display = ["name", "location_type", "parent_location"]
    list_filter = ["location_type"]
    search_fields = ["name"]


@admin.register(InventoryItem)
class InventoryItemAdmin(admin.ModelAdmin):
    list_display = [
        "item_name",
        "product",
        "location",
        "batch_number",
        "quantity",
        "expiry_date",
        "status",
    ]
    list_filter = ["status", "location"]
    search_fields = ["item_name", "batch_number"]


@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    list_display = [
        "inventory_item",
        "movement_type",
        "quantity",
        "from_location",
        "to_location",
        "performed_by",
        "created_at",
    ]
    list_filter = ["movement_type"]
    search_fields = ["inventory_item__item_name"]
