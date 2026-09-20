from importlib import import_module

from django.apps import apps as django_apps
from django.core.exceptions import ValidationError
from rest_framework.test import APITestCase

from .models import Brand, Category, CategoryBrand, Product

# Module name starts with a digit, so it can't be imported with `from ... import`.
backfill_unambiguous_categories = import_module(
    "inverters.migrations.0007_backfill_product_category"
).backfill_unambiguous_categories

PRODUCTS_URL = "/api/inverters/products/"


def product_detail_url(slug):
    return f"/api/inverters/products/{slug}/"


class SharedBrandCategoryTests(APITestCase):
    """A brand placed under two categories must not leak its products across both.

    Fox sits under Ongrid and Hybrid as one brand; its ongrid units belong to
    one tree and its hybrid units to the other, and `Product.category` is what
    keeps them apart.
    """

    def setUp(self):
        self.ongrid = Category.objects.create(name="Ongrid Inverters", slug="ongrid", order=1)
        self.hybrid = Category.objects.create(name="Hybrid Inverters", slug="hybrid", order=2)

        # Shared across both categories.
        self.fox = Brand.objects.create(name="Fox", slug="fox")
        CategoryBrand.objects.create(category=self.ongrid, brand=self.fox)
        CategoryBrand.objects.create(category=self.hybrid, brand=self.fox)

        # Ongrid only.
        self.crown = Brand.objects.create(name="Crown", slug="crown")
        CategoryBrand.objects.create(category=self.ongrid, brand=self.crown)

        self.fox_ongrid = Product.objects.create(
            brand=self.fox,
            category=self.ongrid,
            name="Fox 5kW Ongrid",
            slug="fox-5kw-ongrid",
            price="150000.00",
        )
        self.fox_hybrid = Product.objects.create(
            brand=self.fox,
            category=self.hybrid,
            name="Fox 6kW Hybrid",
            slug="fox-6kw-hybrid",
            price="185000.00",
        )

    def test_category_filter_splits_a_shared_brands_products(self):
        ongrid = self.client.get(PRODUCTS_URL, {"category": "ongrid"})
        hybrid = self.client.get(PRODUCTS_URL, {"category": "hybrid"})

        self.assertEqual([p["slug"] for p in ongrid.data], ["fox-5kw-ongrid"])
        self.assertEqual([p["slug"] for p in hybrid.data], ["fox-6kw-hybrid"])

    def test_category_and_brand_filter_together(self):
        res = self.client.get(PRODUCTS_URL, {"category": "hybrid", "brand": "fox"})

        self.assertEqual([p["slug"] for p in res.data], ["fox-6kw-hybrid"])

    def test_single_category_brand_needs_no_category_picked(self):
        product = Product.objects.create(
            brand=self.crown,
            name="Crown 3kW Ongrid",
            slug="crown-3kw-ongrid",
            price="90000.00",
        )

        self.assertEqual(product.category, self.ongrid)

    def test_sub_variant_inherits_the_parents_only_placement(self):
        single_phase = Brand.objects.create(name="Single Phase", slug="crown-single-phase", parent=self.crown)

        product = Product.objects.create(
            brand=single_phase,
            name="Crown 2kW Single Phase",
            slug="crown-2kw-single-phase",
            price="70000.00",
        )

        self.assertEqual(product.category, self.ongrid)

    def test_shared_brand_without_a_category_is_rejected(self):
        product = Product(brand=self.fox, name="Fox 8kW", slug="fox-8kw", price="200000.00")

        with self.assertRaises(ValidationError) as ctx:
            product.full_clean()

        message = ctx.exception.message_dict["category"][0]
        self.assertIn("Ongrid Inverters", message)
        self.assertIn("Hybrid Inverters", message)

    def test_category_the_brand_isnt_placed_in_is_rejected(self):
        product = Product(
            brand=self.crown,
            category=self.hybrid,
            name="Crown 4kW",
            slug="crown-4kw",
            price="95000.00",
        )

        with self.assertRaises(ValidationError) as ctx:
            product.full_clean()

        self.assertIn("only placed in Ongrid Inverters", ctx.exception.message_dict["category"][0])

    def test_breadcrumb_names_the_products_own_category(self):
        res = self.client.get(product_detail_url("fox-6kw-hybrid"))

        self.assertEqual(res.data["categories"], ["Madni Solar", "Inverters", "Hybrid Inverters", "Fox"])

    def test_deleting_a_category_keeps_its_products(self):
        self.hybrid.delete()
        self.fox_hybrid.refresh_from_db()

        self.assertIsNone(self.fox_hybrid.category)

    def test_product_without_a_category_still_shows_under_its_brands_placements(self):
        # Transitional fallback for rows that predate the field - drops out
        # once the fallback branch in the view is removed.
        Product.objects.filter(pk=self.fox_hybrid.pk).update(category=None)

        ongrid = self.client.get(PRODUCTS_URL, {"category": "ongrid"})
        hybrid = self.client.get(PRODUCTS_URL, {"category": "hybrid"})

        self.assertIn("fox-6kw-hybrid", [p["slug"] for p in ongrid.data])
        self.assertIn("fox-6kw-hybrid", [p["slug"] for p in hybrid.data])


class BackfillMigrationTests(APITestCase):
    """The 0007 backfill fills only what the data decides unambiguously.

    Calls the migration's function against the live app registry - the model
    shapes it touches are unchanged since 0007, so the historical registry
    would behave identically here.
    """

    def setUp(self):
        self.ongrid = Category.objects.create(name="Ongrid Inverters", slug="ongrid", order=1)
        self.hybrid = Category.objects.create(name="Hybrid Inverters", slug="hybrid", order=2)

        self.fox = Brand.objects.create(name="Fox", slug="fox")
        CategoryBrand.objects.create(category=self.ongrid, brand=self.fox)
        CategoryBrand.objects.create(category=self.hybrid, brand=self.fox)

        self.crown = Brand.objects.create(name="Crown", slug="crown")
        CategoryBrand.objects.create(category=self.ongrid, brand=self.crown)

        self.knox = Brand.objects.create(name="Knox", slug="knox")  # placed nowhere

        self.crown_single = Brand.objects.create(
            name="Single Phase", slug="crown-single-phase", parent=self.crown
        )

        # Stand in for rows that predate the field - bypass save()'s auto-fill
        # the same way an already-stored row does.
        self.products = {}
        for key, brand in [
            ("crown", self.crown),
            ("fox", self.fox),
            ("knox", self.knox),
            ("crown_single", self.crown_single),
        ]:
            product = Product.objects.create(
                brand=brand, name=f"{key} unit", slug=f"{key}-unit", price="1000.00"
            )
            Product.objects.filter(pk=product.pk).update(category=None)
            self.products[key] = product

    def test_backfill(self):
        backfill_unambiguous_categories(django_apps, None)

        for product in self.products.values():
            product.refresh_from_db()

        # One placement -> filled.
        self.assertEqual(self.products["crown"].category, self.ongrid)
        # Sub-variant takes the parent's one placement.
        self.assertEqual(self.products["crown_single"].category, self.ongrid)
        # Two placements -> left for an admin to pick.
        self.assertIsNone(self.products["fox"].category)
        # No placement -> nothing to fill in.
        self.assertIsNone(self.products["knox"].category)
