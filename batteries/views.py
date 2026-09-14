from django.http import Http404
from rest_framework.exceptions import NotFound
from rest_framework.generics import ListAPIView, RetrieveAPIView

from .models import Brand, Product
from .serializers import BrandNodeSerializer, ProductDetailSerializer, ProductListSerializer


class BatteryBrandListView(ListAPIView):
    """GET /api/batteries/brands/ - public, read-only, no throttle.

    Same reasoning as solar_panels/inverters - catalog browsing, not a form
    submission, so the anon throttle doesn't apply. Only top-level brands are
    queried; each one recursively serializes its own `sub` (see BrandNodeSerializer).
    """

    queryset = Brand.objects.filter(parent__isnull=True)
    serializer_class = BrandNodeSerializer
    throttle_classes = []
    permission_classes = []
    authentication_classes = []


class BatteryProductListView(ListAPIView):
    """GET /api/batteries/products/  (optional ?brand=<slug>) - public, read-only."""

    serializer_class = ProductListSerializer
    throttle_classes = []
    permission_classes = []
    authentication_classes = []

    def get_queryset(self):
        queryset = Product.objects.select_related("brand")
        brand_slug = self.request.query_params.get("brand")
        if brand_slug:
            queryset = queryset.filter(brand__slug=brand_slug)
        return queryset


class BatteryProductDetailView(RetrieveAPIView):
    """GET /api/batteries/products/<slug>/ - public, read-only.

    `slug` here is the product's own (battery-prefixed) slug, not the brand slug.
    """

    queryset = Product.objects.select_related("brand")
    serializer_class = ProductDetailSerializer
    lookup_field = "slug"
    throttle_classes = []
    permission_classes = []
    authentication_classes = []

    def get_object(self):
        # Same normalization as solar_panels/inverters - plain
        # {"detail": "Not found."} instead of DRF's default model-specific message.
        try:
            return super().get_object()
        except Http404:
            raise NotFound()
