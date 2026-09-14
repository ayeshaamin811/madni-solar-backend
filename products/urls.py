from django.urls import path

from .views import (
    ProductCategoryListView,
    ProductDetailView,
    ProductListView,
)

urlpatterns = [
    path("products/categories/", ProductCategoryListView.as_view(), name="product-categories"),
    path("products/products/", ProductListView.as_view(), name="product-products"),
    path(
        "products/products/<slug:slug>/",
        ProductDetailView.as_view(),
        name="product-product-detail",
    ),
]
