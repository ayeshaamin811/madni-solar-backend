from django.db.models import Q
from django.http import Http404
from rest_framework.exceptions import NotFound
from rest_framework.generics import ListAPIView, RetrieveAPIView

from .models import Category, Product
from .serializers import CategorySerializer, ProductDetailSerializer, ProductListSerializer


class InverterCategoryListView(ListAPIView):
    """GET /api/inverters/categories/ - public, read-only, no throttle.

    Same reasoning as solar_panels' brand list view - this is catalog
    browsing, not a form submission, so the anon throttle doesn't apply.
    """

    queryset = Category.objects.all().prefetch_related(
        "category_brands__brand__sub_variants",
    )
    serializer_class = CategorySerializer
    throttle_classes = []
    permission_classes = []
    authentication_classes = []


class InverterProductListView(ListAPIView):
    """GET /api/inverters/products/  (optional ?category=<slug>&brand=<slug>) - public, read-only."""

    serializer_class = ProductListSerializer
    throttle_classes = []
    permission_classes = []
    authentication_classes = []

    def get_queryset(self):
        queryset = Product.objects.select_related("brand", "brand__parent")
        category_slug = self.request.query_params.get("category")
        brand_slug = self.request.query_params.get("brand")

        if category_slug:
            queryset = queryset.filter(
                Q(brand__category_links__category__slug=category_slug)
                | Q(brand__parent__category_links__category__slug=category_slug)
            ).distinct()
        if brand_slug:
            queryset = queryset.filter(brand__slug=brand_slug)
        return queryset


class InverterProductDetailView(RetrieveAPIView):
    """GET /api/inverters/products/<slug>/ - public, read-only."""

    queryset = Product.objects.select_related("brand", "brand__parent")
    serializer_class = ProductDetailSerializer
    lookup_field = "slug"
    throttle_classes = []
    permission_classes = []
    authentication_classes = []

    def get_object(self):
        # Same normalization as solar_panels - plain {"detail": "Not found."}
        # instead of DRF's default model-specific message.
        try:
            return super().get_object()
        except Http404:
            raise NotFound()
