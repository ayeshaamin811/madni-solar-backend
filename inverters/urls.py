from django.urls import path

from .views import (
    InverterCategoryListView,
    InverterProductDetailView,
    InverterProductListView,
)

urlpatterns = [
    path("inverters/categories/", InverterCategoryListView.as_view(), name="inverter-categories"),
    path("inverters/products/", InverterProductListView.as_view(), name="inverter-products"),
    path(
        "inverters/products/<slug:slug>/",
        InverterProductDetailView.as_view(),
        name="inverter-product-detail",
    ),
]
