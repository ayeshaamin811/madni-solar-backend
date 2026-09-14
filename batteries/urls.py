from django.urls import path

from .views import (
    BatteryBrandListView,
    BatteryProductDetailView,
    BatteryProductListView,
)

urlpatterns = [
    path("batteries/brands/", BatteryBrandListView.as_view(), name="battery-brands"),
    path("batteries/products/", BatteryProductListView.as_view(), name="battery-products"),
    path(
        "batteries/products/<slug:slug>/",
        BatteryProductDetailView.as_view(),
        name="battery-product-detail",
    ),
]
