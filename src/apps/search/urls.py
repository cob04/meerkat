from django.urls import path

from apps.search import views

app_name = "search"

urlpatterns = [
    path("", views.catalog_search, name="catalog-search"),
    path("availability/", views.availability, name="availability"),
    path("expiry/", views.expiry, name="expiry"),
    path("stock/", views.low_stock, name="low-stock"),
    path("recall/", views.recall_lookup, name="recall-lookup"),
    path("insights/value/", views.inventory_value, name="inventory-value"),
    path("insights/value-at-risk/", views.value_at_risk, name="value-at-risk"),
    path("insights/coverage/", views.network_coverage, name="network-coverage"),
]
