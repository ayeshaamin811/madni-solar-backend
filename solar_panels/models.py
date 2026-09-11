from django.db import models

from backend.image_utils import compress_field_file

# Brand logos are small to begin with; product photos need a bit more room
# for the detail page. Both get re-encoded to a compact JPEG on save so a
# raw camera/DSLR upload from the admin doesn't sit on disk at full size.
BRAND_IMAGE_MAX_DIMENSION = 800
PRODUCT_IMAGE_MAX_DIMENSION = 1200
IMAGE_QUALITY = 82


class Brand(models.Model):
    name = models.CharField(max_length=120)
    slug = models.SlugField(max_length=140, unique=True)
    description = models.TextField(blank=True)
    image = models.ImageField(upload_to="solar_panels/brands/", null=True, blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        # SlugField doesn't normalize case on its own - a manually-typed slug
        # with capitals (instead of the admin's auto-populate-from-name JS)
        # silently breaks the detail URL, since /brands/<slug>/ lookups are
        # case-sensitive.
        self.slug = self.slug.lower()
        self.image = compress_field_file(
            self.image, max_dimension=BRAND_IMAGE_MAX_DIMENSION, quality=IMAGE_QUALITY
        )
        super().save(*args, **kwargs)


class Product(models.Model):
    brand = models.ForeignKey(Brand, on_delete=models.CASCADE, related_name="products")
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    image = models.ImageField(upload_to="solar_panels/products/", null=True, blank=True)
    short_description = models.TextField(blank=True)

    # Plain text in the admin - paste one or more paragraphs, no brackets or
    # quotes needed. A blank line between paragraphs splits them into the
    # array the API returns (see ProductDetailSerializer.get_description);
    # one paragraph with no blank line just becomes a single-item array.
    description = models.TextField(
        blank=True, help_text="Paste the paragraph(s) as plain text. Separate multiple paragraphs with a blank line."
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["brand__name", "name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        # Same reasoning as Brand.save() - keeps /products/<slug>/ lookups
        # from silently breaking on a manually-typed, mixed-case slug.
        self.slug = self.slug.lower()
        self.image = compress_field_file(
            self.image, max_dimension=PRODUCT_IMAGE_MAX_DIMENSION, quality=IMAGE_QUALITY
        )
        super().save(*args, **kwargs)
