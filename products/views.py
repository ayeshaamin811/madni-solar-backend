from django.http import Http404
from rest_framework.exceptions import NotFound
from rest_framework.generics import ListAPIView, RetrieveAPIView

from .models import Category, Product
from .serializers import CategorySerializer, ProductDetailSerializer, ProductListSerializer


class ProductCategoryListView(ListAPIView):
    """GET /api/products/categories/ - public, read-only, no throttle.

    Same reasoning as the other catalogue apps - catalog browsing, not a
    form submission, so the anon throttle doesn't apply.
    """

    queryset = Category.objects.all().prefetch_related("items__sub_items")
    serializer_class = CategorySerializer
    throttle_classes = []
    permission_classes = []
    authentication_classes = []


class ProductListView(ListAPIView):
    """GET /api/products/products/  (optional ?category=<slug>&item=<slug>) - public, read-only.

    `?item=` alone can match more than one product, since item slugs repeat
    across categories (e.g. "huawei" under both Packages and Product
    Accessories) - combine with `?category=` for exactly one.
    """

    serializer_class = ProductListSerializer
    throttle_classes = []
    permission_classes = []
    authentication_classes = []

    def get_queryset(self):
        queryset = Product.objects.select_related("item", "item__category")
        category_slug = self.request.query_params.get("category")
        item_slug = self.request.query_params.get("item")

        if category_slug:
            queryset = queryset.filter(item__category__slug=category_slug)
        if item_slug:
            queryset = queryset.filter(item__slug=item_slug)
        return queryset


class ProductDetailView(RetrieveAPIView):
    """GET /api/products/products/<slug>/ - public, read-only.

    `slug` here is the product's own (category-prefixed) slug, not the item slug.
    """

    queryset = Product.objects.select_related("item", "item__category")
    serializer_class = ProductDetailSerializer
    lookup_field = "slug"
    throttle_classes = []
    permission_classes = []
    authentication_classes = []

    def get_object(self):
        # Same normalization as the other catalogue apps - plain
        # {"detail": "Not found."} instead of DRF's default model-specific message.
        try:
            return super().get_object()
        except Http404:
            raise NotFound()
