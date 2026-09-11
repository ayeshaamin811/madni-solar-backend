from rest_framework import serializers

from .models import Brand, Product


class BrandSerializer(serializers.ModelSerializer):
    image = serializers.SerializerMethodField()

    class Meta:
        model = Brand
        fields = ["name", "slug", "description", "image"]

    def get_image(self, obj):
        return _absolute_image_url(obj.image, self.context.get("request"))


class ProductListSerializer(serializers.ModelSerializer):
    """Light fields for the listing pages (/solar-panels, /solar-panels/:brandSlug)."""

    brandSlug = serializers.SlugRelatedField(source="brand", slug_field="slug", read_only=True)
    price = serializers.DecimalField(max_digits=10, decimal_places=2, coerce_to_string=False)
    image = serializers.SerializerMethodField()
    shortDescription = serializers.CharField(source="short_description")

    class Meta:
        model = Product
        fields = ["name", "slug", "brandSlug", "price", "image", "shortDescription"]

    def get_image(self, obj):
        return _absolute_image_url(obj.image, self.context.get("request"))


class ProductDetailSerializer(ProductListSerializer):
    """Full fields for the product detail page - adds description."""

    description = serializers.SerializerMethodField()

    class Meta(ProductListSerializer.Meta):
        fields = ProductListSerializer.Meta.fields + ["description"]

    def get_description(self, obj):
        # obj.description is plain text in the admin (see the model field's
        # help_text) - a blank line between paragraphs is what splits them
        # into the array the frontend renders as separate <p> tags.
        if not obj.description:
            return []
        return [
            " ".join(paragraph.split())
            for paragraph in obj.description.split("\n\n")
            if paragraph.strip()
        ]


def _absolute_image_url(image_field, request):
    if not image_field:
        return ""
    return request.build_absolute_uri(image_field.url) if request else image_field.url
