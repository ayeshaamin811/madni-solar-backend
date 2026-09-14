from rest_framework import serializers

from .models import Category, Item, Product


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


class ItemNodeSerializer(serializers.ModelSerializer):
    """A node in a category's tree - recursively serializes its own `sub`, any depth."""

    image = serializers.SerializerMethodField()
    sub = serializers.SerializerMethodField()

    class Meta:
        model = Item
        fields = ["name", "slug", "description", "image", "sub"]

    def get_image(self, obj):
        return _absolute_image_url(obj.image, self.context.get("request"))

    def get_sub(self, obj):
        children = obj.sub_items.all().order_by("order", "name")
        return ItemNodeSerializer(children, many=True, context=self.context).data


class CategorySerializer(serializers.ModelSerializer):
    items = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = ["name", "slug", "description", "items"]

    def get_items(self, obj):
        top_level = obj.items.filter(parent__isnull=True).order_by("order", "name")
        return ItemNodeSerializer(top_level, many=True, context=self.context).data


class ProductListSerializer(serializers.ModelSerializer):
    """Light fields for the listing pages (/products, /products/:category, /products/:category/:itemSlug)."""

    brandSlug = serializers.SlugRelatedField(source="item", slug_field="slug", read_only=True)
    categorySlug = serializers.SerializerMethodField()
    price = serializers.DecimalField(max_digits=10, decimal_places=2, coerce_to_string=False)
    image = serializers.SerializerMethodField()
    shortDescription = serializers.CharField(source="short_description")

    class Meta:
        model = Product
        fields = ["name", "slug", "brandSlug", "categorySlug", "price", "image", "shortDescription"]

    def get_categorySlug(self, obj):
        return obj.item.category.slug

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
        # Breadcrumb: Madni Solar / Products / <category name> / <ancestor items...> / <item name>.
        item = obj.item
        chain = []
        node = item
        while node is not None:
            chain.append(node.name)
            node = node.parent
        chain.reverse()
        return ["Madni Solar", "Products", item.category.name] + chain
