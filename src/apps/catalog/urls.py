from django.urls import path

from apps.catalog import views

app_name = "catalog"

urlpatterns = [
    path("inventory/", views.inventory_list, name="inventory-list"),
    path("inventory/<int:pk>/", views.inventory_detail, name="inventory-detail"),
    path("inventory/receive/", views.receive_stock_view, name="inventory-receive"),
    path("inventory/<int:pk>/dispense/", views.dispense_stock_view, name="inventory-dispense"),
    path("inventory/<int:pk>/transfer/", views.transfer_stock_view, name="inventory-transfer"),
    path("inventory/<int:pk>/adjust/", views.adjust_stock_view, name="inventory-adjust"),
    path("inventory/<int:pk>/return/", views.return_stock_view, name="inventory-return"),
    path("inventory/recall/", views.recall_batch_view, name="inventory-recall"),
    path("locations/", views.location_list, name="location-list"),
    path("products/", views.product_list, name="product-list"),
]
