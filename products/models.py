from django.core.exceptions import ValidationError
from django.db import models
from django.utils.text import slugify

from backend.image_utils import compress_field_file

# Same reasoning as the other catalogue apps - item photos are small,
# product photos need a bit more room for the detail page.
ITEM_IMAGE_MAX_DIMENSION = 800
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


class Item(models.Model):
    """A node in a category's tree - arbitrary depth via self-referential `parent`.

    Every node carries `category` directly (not just roots), so filtering by
    category doesn't require walking the tree. The same item name can exist
    in two different categories on purpose (e.g. "Huawei" under both
    Packages and Product Accessories) - these are independent rows, not a
    shared entity, so `slug` is only unique within a category (see Meta),
    not globally.
    """

    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name="items")
    parent = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.CASCADE, related_name="sub_items"
    )
    name = models.CharField(max_length=120)
    slug = models.SlugField(max_length=200)
    description = models.TextField(blank=True)
    image = models.ImageField(upload_to="products/items/", null=True, blank=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "name"]
        unique_together = ("category", "slug")

    def __str__(self):
        return f"{self.parent} -> {self.name}" if self.parent else f"{self.category.name} / {self.name}"

    def clean(self):
        # A node set as its own (or an ancestor's) parent would make
        # __str__ - and any tree walk - recurse forever.
        node = self.parent
        while node is not None:
            if node.pk == self.pk:
                raise ValidationError({"parent": "An item can't be its own ancestor."})
            node = node.parent

    def save(self, *args, **kwargs):
        if self.parent_id:
            # A child always belongs to its parent's category - keeps the
            # tree from disagreeing with itself about category membership,
            # so admins adding a sub-item never have to pick it manually.
            self.category_id = self.parent.category_id
        self.slug = self.slug.lower()
        self.image = compress_field_file(
            self.image, max_dimension=ITEM_IMAGE_MAX_DIMENSION, quality=IMAGE_QUALITY
        )
        super().save(*args, **kwargs)


class Product(models.Model):
    # A ForeignKey, not OneToOne - an item can carry more than one product,
    # same relaxation as inverters/batteries.
    item = models.ForeignKey(Item, on_delete=models.CASCADE, related_name="products")
    name = models.CharField(max_length=200)

    # Prefixed with the item's category slug (see save()) since item slugs
    # repeat across categories (e.g. "huawei" under both Packages and
    # Product Accessories) - this is what makes the product slug unique.
    slug = models.SlugField(
        max_length=240,
        unique=True,
        blank=True,
        help_text="Leave blank to auto-fill as '<category slug>-<product name>'.",
    )
    price = models.DecimalField(max_digits=10, decimal_places=2)
    image = models.ImageField(upload_to="products/products/", null=True, blank=True)
    short_description = models.TextField(blank=True)

    # Same convention as the other catalogue apps - plain text, a blank line
    # between paragraphs splits them into the array the API returns.
    description = models.TextField(
        blank=True, help_text="Paste the paragraph(s) as plain text. Separate multiple paragraphs with a blank line."
    )
    why_choose = models.TextField(blank=True, help_text="One short checklist item per line.")

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["item__name", "name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = f"{self.item.category.slug}-{slugify(self.name)}"
        self.slug = self.slug.lower()
        self.image = compress_field_file(
            self.image, max_dimension=PRODUCT_IMAGE_MAX_DIMENSION, quality=IMAGE_QUALITY
        )
        super().save(*args, **kwargs)
