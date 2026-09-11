from django.urls import path

from .views import (
    SolarPanelBrandListView,
    SolarPanelProductDetailView,
    SolarPanelProductListView,
)

urlpatterns = [
    path("solar-panels/brands/", SolarPanelBrandListView.as_view(), name="solar-panel-brands"),
    path("solar-panels/products/", SolarPanelProductListView.as_view(), name="solar-panel-products"),
    path(
        "solar-panels/products/<slug:slug>/",
        SolarPanelProductDetailView.as_view(),
        name="solar-panel-product-detail",
    ),
]
