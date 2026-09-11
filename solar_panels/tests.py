import io
import shutil
import tempfile

from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from PIL import Image
from rest_framework.test import APITestCase

from .models import Brand, Product

BRANDS_URL = "/api/solar-panels/brands/"
PRODUCTS_URL = "/api/solar-panels/products/"


def product_detail_url(slug):
    return f"/api/solar-panels/products/{slug}/"


def make_test_image(name="brand.png", size=(100, 100)):
    buffer = io.BytesIO()
    Image.new("RGB", size, (10, 20, 30)).save(buffer, format="PNG")
    return SimpleUploadedFile(name, buffer.getvalue(), content_type="image/png")


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class SolarPanelsAPITests(APITestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(settings.MEDIA_ROOT, ignore_errors=True)

    def setUp(self):
        self.yingli = Brand.objects.create(name="Yingli", slug="yingli", description="")
        self.astronergy = Brand.objects.create(name="Astronergy", slug="astronergy")

        self.yingli_product = Product.objects.create(
            brand=self.yingli,
            name="Yingli Solar 550W Mono Panel",
            slug="yingli-solar-550w-mono-panel",
            price="18500.00",
            short_description="High-efficiency monocrystalline panel.",
            description="Paragraph one.\n\nParagraph two.\n\nParagraph three.",
        )
        self.astronergy_product = Product.objects.create(
            brand=self.astronergy,
            name="Astronergy 450W Panel",
            slug="astronergy-450w-panel",
            price="15000.00",
        )

    def test_list_brands(self):
        res = self.client.get(BRANDS_URL)

        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.data), 2)
        # Ordered by name -> Astronergy before Yingli.
        self.assertEqual(res.data[0]["slug"], "astronergy")
        self.assertEqual(
            set(res.data[0].keys()), {"name", "slug", "description", "image"}
        )
        self.assertEqual(res.data[0]["image"], "")

    def test_list_products_returns_light_fields(self):
        res = self.client.get(PRODUCTS_URL)

        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.data), 2)
        item = next(p for p in res.data if p["slug"] == "yingli-solar-550w-mono-panel")
        self.assertEqual(
            set(item.keys()),
            {"name", "slug", "brandSlug", "price", "image", "shortDescription"},
        )
        self.assertEqual(item["brandSlug"], "yingli")
        self.assertEqual(float(item["price"]), 18500.00)
        self.assertNotIn("description", item)

    def test_list_products_filters_by_brand(self):
        res = self.client.get(PRODUCTS_URL, {"brand": "yingli"})

        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.data), 1)
        self.assertEqual(res.data[0]["slug"], "yingli-solar-550w-mono-panel")

    def test_list_products_unknown_brand_returns_empty(self):
        res = self.client.get(PRODUCTS_URL, {"brand": "does-not-exist"})

        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data, [])

    def test_product_detail_returns_full_fields(self):
        res = self.client.get(product_detail_url("yingli-solar-550w-mono-panel"))

        self.assertEqual(res.status_code, 200)
        self.assertEqual(
            set(res.data.keys()),
            {"name", "slug", "brandSlug", "price", "image", "shortDescription", "description"},
        )
        self.assertEqual(res.data["description"], ["Paragraph one.", "Paragraph two.", "Paragraph three."])

    def test_description_single_paragraph_with_no_blank_line(self):
        self.astronergy_product.description = "Just one plain paragraph, pasted as-is."
        self.astronergy_product.save()

        res = self.client.get(product_detail_url("astronergy-450w-panel"))

        self.assertEqual(res.data["description"], ["Just one plain paragraph, pasted as-is."])

    def test_description_collapses_line_wraps_within_a_paragraph(self):
        # Text pasted from Word/Docs often keeps a newline at each line wrap
        # even though it's still one paragraph - those should collapse to a
        # single space, not split into separate array items.
        self.astronergy_product.description = "This is line one\nand this is line two of the same paragraph."
        self.astronergy_product.save()

        res = self.client.get(product_detail_url("astronergy-450w-panel"))

        self.assertEqual(
            res.data["description"],
            ["This is line one and this is line two of the same paragraph."],
        )

    def test_description_empty_returns_empty_list(self):
        res = self.client.get(product_detail_url("astronergy-450w-panel"))

        self.assertEqual(res.data["description"], [])

    def test_product_detail_not_found(self):
        res = self.client.get(product_detail_url("does-not-exist"))

        self.assertEqual(res.status_code, 404)
        self.assertEqual(res.data, {"detail": "Not found."})

    def test_image_url_is_absolute_when_present(self):
        self.yingli.image = make_test_image()
        self.yingli.save()

        res = self.client.get(BRANDS_URL)

        yingli_data = next(b for b in res.data if b["slug"] == "yingli")
        self.assertTrue(yingli_data["image"].startswith("http"))
        self.assertIn("/media/solar_panels/brands/", yingli_data["image"])

    def test_slug_is_lowercased_on_save(self):
        # A manually-typed, mixed-case slug (bypassing the admin's
        # auto-populate-from-name JS) used to make /products/<slug>/ 404
        # forever, since the lookup is case-sensitive.
        brand = Brand.objects.create(name="Mixed Case Brand", slug="Mixed-Case-Brand")
        product = Product.objects.create(
            brand=brand, name="Weird Casing Panel", slug="Weird-Casing-Panel", price="1000.00"
        )

        self.assertEqual(brand.slug, "mixed-case-brand")
        self.assertEqual(product.slug, "weird-casing-panel")
        self.assertEqual(self.client.get(product_detail_url(product.slug)).status_code, 200)

    def test_no_auth_required(self):
        self.assertEqual(self.client.get(BRANDS_URL).status_code, 200)
        self.assertEqual(self.client.get(PRODUCTS_URL).status_code, 200)
        self.assertEqual(
            self.client.get(product_detail_url("yingli-solar-550w-mono-panel")).status_code, 200
        )

    def test_brand_image_is_compressed_on_save(self):
        self.yingli.image = make_test_image(size=(2000, 1500))
        original_size = self.yingli.image.size
        self.yingli.save()

        self.assertTrue(self.yingli.image.name.endswith(".jpg"))
        with self.yingli.image.open("rb") as f:
            image = Image.open(f)
            image.load()
            self.assertLessEqual(max(image.size), 800)
        self.assertLess(self.yingli.image.size, original_size)

    def test_product_image_is_compressed_on_save(self):
        self.yingli_product.image = make_test_image(name="product.png", size=(3000, 2000))
        original_size = self.yingli_product.image.size
        self.yingli_product.save()

        self.assertTrue(self.yingli_product.image.name.endswith(".jpg"))
        with self.yingli_product.image.open("rb") as f:
            image = Image.open(f)
            image.load()
            self.assertLessEqual(max(image.size), 1200)
        self.assertLess(self.yingli_product.image.size, original_size)

    def test_resaving_without_a_new_image_does_not_recompress(self):
        self.yingli.image = make_test_image(size=(2000, 1500))
        self.yingli.save()
        stored_name = self.yingli.image.name

        self.yingli.description = "updated"
        self.yingli.save()

        self.assertEqual(self.yingli.image.name, stored_name)

    def test_browsing_is_not_throttled(self):
        # The global AnonRateThrottle default is 60/hour; these read-only
        # views opt out of it, so many rapid requests should all pass.
        for _ in range(65):
            res = self.client.get(PRODUCTS_URL)
            self.assertEqual(res.status_code, 200)
