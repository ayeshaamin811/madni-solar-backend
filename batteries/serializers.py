from rest_framework import serializers

from .models import Brand, Product


def _absolute_image_url(image_field, request):
    if not image_field:
        return ""
    return request.build_absolute_uri(image_field.url) if request else image_field.url


def _split_lines(text):
    return [line.strip() for line in text.splitlines() if line.strip()]


def _split_paragraphs(text):
    if not text:
        return []
    return [" ".join(paragraph.split()) for paragraph in text.split("\n\n") if paragraph.strip()]


class BrandNodeSerializer(serializers.ModelSerializer):
    """A node in the tree - recursively serializes its own `sub`, any depth."""

    image = serializers.SerializerMethodField()
    sub = serializers.SerializerMethodField()

    class Meta:
        model = Brand
        fields = ["name", "slug", "description", "image", "sub"]

    def get_image(self, obj):
        return _absolute_image_url(obj.image, self.context.get("request"))

    def get_sub(self, obj):
        children = obj.sub_variants.all().order_by("order", "name")
        return BrandNodeSerializer(children, many=True, context=self.context).data


class ProductListSerializer(serializers.ModelSerializer):
    """Light fields for the listing page (/batteries)."""

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
    """Full fields for the product detail page."""

    description = serializers.SerializerMethodField()
    whyChoose = serializers.SerializerMethodField()
    categories = serializers.SerializerMethodField()

    class Meta(ProductListSerializer.Meta):
        fields = ProductListSerializer.Meta.fields + ["description", "whyChoose", "categories"]

    def get_description(self, obj):
        return _split_paragraphs(obj.description)

    def get_whyChoose(self, obj):
        return _split_lines(obj.why_choose)

    def get_categories(self, obj):
        # Breadcrumb: Madni Solar / Batteries / <ancestor brands...> / <node>.
        chain = []
        node = obj.brand
        while node is not None:
            chain.append(node.name)
            node = node.parent
        chain.reverse()
        return ["Madni Solar", "Batteries"] + chain
