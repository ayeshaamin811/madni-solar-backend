from rest_framework import serializers

from .models import Brand, Category, Product


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


class SubVariantSerializer(serializers.ModelSerializer):
    """A leaf sub-variant node (e.g. Inverex -> Single Phase) - no `sub` key, it has none."""

    image = serializers.SerializerMethodField()

    class Meta:
        model = Brand
        fields = ["name", "slug", "description", "image"]

    def get_image(self, obj):
        return _absolute_image_url(obj.image, self.context.get("request"))


class BrandNodeSerializer(serializers.ModelSerializer):
    """A top-level brand node inside a category's tree - always carries `sub`."""

    image = serializers.SerializerMethodField()
    sub = serializers.SerializerMethodField()

    class Meta:
        model = Brand
        fields = ["name", "slug", "description", "image", "sub"]

    def get_image(self, obj):
        return _absolute_image_url(obj.image, self.context.get("request"))

    def get_sub(self, obj):
        sub_variants = obj.sub_variants.all().order_by("order", "name")
        return SubVariantSerializer(sub_variants, many=True, context=self.context).data


class CategorySerializer(serializers.ModelSerializer):
    brands = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = ["name", "slug", "description", "brands"]

    def get_brands(self, obj):
        category_brands = obj.category_brands.select_related("brand").order_by("order")
        brands = [cb.brand for cb in category_brands]
        return BrandNodeSerializer(brands, many=True, context=self.context).data


class ProductListSerializer(serializers.ModelSerializer):
    """Light fields for the listing pages (/inverters, /inverters/:category, /inverters/:category/:brandSlug)."""

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
        # Breadcrumb: Madni Solar / Inverters / <Category> / [<Parent brand> /] <Item>.
        # A shared brand (e.g. Fox, placed under two categories) resolves to
        # whichever category sorts first - fine for a breadcrumb, which just
        # needs one valid path, not every path.
        brand = obj.brand
        trail = ["Madni Solar", "Inverters"]

        node = brand.parent or brand
        category_link = (
            node.category_links.select_related("category").order_by("category__order", "order").first()
        )
        if category_link:
            trail.append(category_link.category.name)
        if brand.parent:
            trail.append(brand.parent.name)
        trail.append(brand.name)
        return trail
