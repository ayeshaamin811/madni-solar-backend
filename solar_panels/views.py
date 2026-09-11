from django.http import Http404
from rest_framework.exceptions import NotFound
from rest_framework.generics import ListAPIView, RetrieveAPIView

from .models import Brand, Product
from .serializers import BrandSerializer, ProductDetailSerializer, ProductListSerializer


class SolarPanelBrandListView(ListAPIView):
    """GET /api/solar-panels/brands/ - public, read-only, no throttle.

    Throttling is turned off here (the global AnonRateThrottle default is
    meant for form submissions like contact/calculator, not for someone
    browsing a product catalog).
    """

    queryset = Brand.objects.all()
    serializer_class = BrandSerializer
    throttle_classes = []
    permission_classes = []
    authentication_classes = []


class SolarPanelProductListView(ListAPIView):
    """GET /api/solar-panels/products/  (optional ?brand=<brandSlug>) - public, read-only."""

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


class SolarPanelProductDetailView(RetrieveAPIView):
    """GET /api/solar-panels/products/<slug>/ - public, read-only."""

    queryset = Product.objects.select_related("brand")
    serializer_class = ProductDetailSerializer
    lookup_field = "slug"
    throttle_classes = []
    permission_classes = []
    authentication_classes = []

    def get_object(self):
        # Django's get_object_or_404() raises a model-specific message ("No
        # Product matches the given query.") which DRF forwards verbatim -
        # normalize it to the plain {"detail": "Not found."} the frontend's
        # error parsing expects (see solar_panels app spec).
        try:
            return super().get_object()
        except Http404:
            raise NotFound()
