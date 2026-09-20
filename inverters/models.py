from django.core.exceptions import ValidationError
from django.db import models

from backend.image_utils import compress_field_file

# Same reasoning as solar_panels.models - brand/sub-variant photos are small,
# product photos need a bit more room for the detail page.
BRAND_IMAGE_MAX_DIMENSION = 800
PRODUCT_IMAGE_MAX_DIMENSION = 1200
IMAGE_QUALITY = 82


class Category(models.Model):
    name = models.CharField(max_length=120)
    slug = models.SlugField(max_length=140, unique=True)
    description = models.TextField(blank=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "name"]
        verbose_name_plural = "Categories"

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        self.slug = self.slug.lower()
        super().save(*args, **kwargs)


class Brand(models.Model):
    """A brand node in the inverter tree.

    `parent` is set only for sub-variants (e.g. Inverex -> Single Phase). A
    brand with sub-variants (`sub_variants.exists()`) is a parent-only node
    and has no `product`; the product lives on each sub-variant instead. A
    brand can sit under more than one Category - see CategoryBrand - so
    category membership isn't derivable from the slug alone, and a product
    under such a brand carries its own `Product.category`.
    """

    parent = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.CASCADE, related_name="sub_variants"
    )
    name = models.CharField(max_length=120)
    slug = models.SlugField(max_length=160, unique=True)
    description = models.TextField(blank=True)
    image = models.ImageField(upload_to="inverters/brands/", null=True, blank=True)
    order = models.PositiveIntegerField(
        default=0, help_text="Display order among sibling sub-variants under the same parent."
    )

    class Meta:
        ordering = ["order", "name"]

    def __str__(self):
        return f"{self.parent} -> {self.name}" if self.parent else self.name

    def clean(self):
        # A brand set as its own (or an ancestor's) parent would make
        # __str__ - and any tree walk - recurse forever.
        node = self.parent
        while node is not None:
            if node.pk == self.pk:
                raise ValidationError({"parent": "A brand can't be its own ancestor."})
            node = node.parent

    def save(self, *args, **kwargs):
        self.slug = self.slug.lower()
        self.image = compress_field_file(
            self.image, max_dimension=BRAND_IMAGE_MAX_DIMENSION, quality=IMAGE_QUALITY
        )
        super().save(*args, **kwargs)


class CategoryBrand(models.Model):
    """Placement of a top-level Brand inside a Category's tree, with its own order.

    A join row (rather than a plain FK on Brand) so the same Brand can be
    placed under more than one Category - e.g. Fox appears under both Ongrid
    and Hybrid Inverters as one brand. The products underneath are not shared,
    though: each carries its own `Product.category` saying which tree it
    belongs to.
    """

    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name="category_brands")
    brand = models.ForeignKey(Brand, on_delete=models.CASCADE, related_name="category_links")
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order"]
        unique_together = ("category", "brand")
        verbose_name = "Category brand placement"
        verbose_name_plural = "Category brand placements"

    def __str__(self):
        return f"{self.category.name} -> {self.brand.name}"


class Product(models.Model):
    # A ForeignKey, not OneToOne - a brand/sub-variant can carry more than
    # one product (e.g. several capacities/models under the same "Fox").
    brand = models.ForeignKey(Brand, on_delete=models.CASCADE, related_name="products")

    # Which category tree this product belongs to. Needed because a Brand can
    # be placed under more than one Category (see CategoryBrand) - a shared
    # brand like Fox sits under both Ongrid and Hybrid, so the brand alone
    # can't say whether a given product is an ongrid or a hybrid unit.
    #
    # Left blank it is derived in save() from the brand's only placement, so
    # admins adding a product under a single-category brand never pick it by
    # hand; for a brand placed in several categories clean() requires it.
    # SET_NULL (not CASCADE) so deleting a category never takes products with
    # it - they survive with no category and are visible in the admin filter.
    category = models.ForeignKey(
        Category,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="products",
        help_text=(
            "Leave blank unless the brand sits under more than one category "
            "- then pick which one this product belongs to."
        ),
    )
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    image = models.ImageField(upload_to="inverters/products/", null=True, blank=True)
    short_description = models.TextField(blank=True)

    # Same convention as solar_panels.Product.description - plain text, a
    # blank line between paragraphs is what splits them into the array the
    # API returns (see ProductDetailSerializer.get_description).
    description = models.TextField(
        blank=True, help_text="Paste the paragraph(s) as plain text. Separate multiple paragraphs with a blank line."
    )
    why_choose = models.TextField(
        blank=True, help_text="One short checklist item per line."
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["brand__name", "name"]

    def __str__(self):
        return self.name

    def placement_categories(self):
        """Categories this product's brand is actually placed under.

        Only top-level brands carry CategoryBrand rows, so for a product on a
        sub-variant (e.g. Inverex -> Single Phase) it is the parent's
        placements that decide. Returns [] for a brand not placed anywhere yet.
        """
        node = self.brand.parent or self.brand
        return list(
            Category.objects.filter(category_brands__brand=node).order_by("order", "name")
        )

    def clean(self):
        if not self.brand_id:
            return  # `brand` is required; let the field's own error stand.

        categories = self.placement_categories()

        if self.category_id is None:
            # Nothing to derive from, and nothing valid to pick either - let it
            # save unset rather than trapping an admin who hasn't placed the
            # brand under a category yet.
            if len(categories) < 2:
                return
            names = " and ".join(category.name for category in categories)
            raise ValidationError(
                {
                    "category": (
                        f"{self.brand.name} is placed in {names} - pick which one "
                        "this product belongs to."
                    )
                }
            )

        if self.category_id not in [category.pk for category in categories]:
            if not categories:
                raise ValidationError(
                    {
                        "category": (
                            f"{self.brand.name} isn't placed under any category yet - "
                            "add it to one from the category admin first."
                        )
                    }
                )
            names = ", ".join(category.name for category in categories)
            raise ValidationError(
                {"category": f"{self.brand.name} is only placed in {names}."}
            )

    def save(self, *args, **kwargs):
        if self.category_id is None and self.brand_id:
            # Unambiguous placement - fill it in so every product the site
            # filters on carries a category, without asking the admin.
            categories = self.placement_categories()
            if len(categories) == 1:
                self.category = categories[0]
        self.slug = self.slug.lower()
        self.image = compress_field_file(
            self.image, max_dimension=PRODUCT_IMAGE_MAX_DIMENSION, quality=IMAGE_QUALITY
        )
        super().save(*args, **kwargs)
