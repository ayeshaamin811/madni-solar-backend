from django.core.exceptions import ValidationError
from django.db import models
from django.utils.text import slugify

from backend.image_utils import compress_field_file

# Same reasoning as inverters/solar_panels - brand photos are small,
# product photos need a bit more room for the detail page.
BRAND_IMAGE_MAX_DIMENSION = 800
PRODUCT_IMAGE_MAX_DIMENSION = 1200
IMAGE_QUALITY = 82


class Brand(models.Model):
    """A node in the battery tree - arbitrary depth via self-referential `parent`.

    Unlike inverters.Brand, every node here gets its own Product regardless
    of whether it has children (e.g. Huawei has a product AND Huawei -> HV
    has its own separate product).
    """

    parent = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.CASCADE, related_name="sub_variants"
    )
    name = models.CharField(max_length=120)
    slug = models.SlugField(max_length=160, unique=True)
    description = models.TextField(blank=True)
    image = models.ImageField(upload_to="batteries/brands/", null=True, blank=True)
    order = models.PositiveIntegerField(default=0)

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


class Product(models.Model):
    # A ForeignKey, not OneToOne - a brand/sub-variant can carry more than
    # one product (e.g. several capacities/models under the same "Huawei").
    brand = models.ForeignKey(Brand, on_delete=models.CASCADE, related_name="products")
    name = models.CharField(max_length=200)

    # Prefixed with "battery-" (see save()) so this doesn't collide with an
    # inverters product slug for a similarly-named product (e.g. "Huawei"
    # exists in both catalogues) - cart/quote lookup is keyed by slug alone.
    slug = models.SlugField(
        max_length=220,
        unique=True,
        blank=True,
        help_text="Leave blank to auto-fill as 'battery-<product name>'.",
    )
    price = models.DecimalField(max_digits=10, decimal_places=2)
    image = models.ImageField(upload_to="batteries/products/", null=True, blank=True)
    short_description = models.TextField(blank=True)

    # Same convention as inverters/solar_panels - plain text, a blank line
    # between paragraphs splits them into the array the API returns.
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

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = f"battery-{slugify(self.name)}"
        self.slug = self.slug.lower()
        self.image = compress_field_file(
            self.image, max_dimension=PRODUCT_IMAGE_MAX_DIMENSION, quality=IMAGE_QUALITY
        )
        super().save(*args, **kwargs)
