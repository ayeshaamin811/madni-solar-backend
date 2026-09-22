from importlib import import_module

from django.apps import apps as django_apps
from django.core.exceptions import ValidationError
from rest_framework.test import APITestCase

from .models import Brand, Category, CategoryBrand, Product

# Module name starts with a digit, so it can't be imported with `from ... import`.
backfill_unambiguous_categories = import_module(
    "inverters.migrations.0007_backfill_product_category"
).backfill_unambiguous_categories
backfill_unambiguous_brand_categories = import_module(
    "inverters.migrations.0009_backfill_brand_category"
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


CATEGORIES_URL = "/api/inverters/categories/"


class SharedBrandSubVariantTests(APITestCase):
    """A shared parent's sub-variants must not appear under both categories.

    Inverex sits under Ongrid and Hybrid as one brand, and each of its
    sub-variants (Single Phase, Three Phase) belongs to one of the two;
    `Brand.category` is what keeps the two trees apart.
    """

    def setUp(self):
        self.ongrid = Category.objects.create(name="Ongrid Inverters", slug="ongrid", order=1)
        self.hybrid = Category.objects.create(name="Hybrid Inverters", slug="hybrid", order=2)

        self.inverex = Brand.objects.create(name="Inverex", slug="inverex")
        CategoryBrand.objects.create(category=self.ongrid, brand=self.inverex)
        CategoryBrand.objects.create(category=self.hybrid, brand=self.inverex)

        self.crown = Brand.objects.create(name="Crown", slug="crown")
        CategoryBrand.objects.create(category=self.ongrid, brand=self.crown)

        self.ongrid_single = Brand.objects.create(
            name="Single Phase", slug="inverex-ongrid-single", parent=self.inverex,
            category=self.ongrid,
        )
        self.hybrid_three = Brand.objects.create(
            name="Three Phase", slug="inverex-hybrid-three", parent=self.inverex,
            category=self.hybrid,
        )

    def _sub_slugs(self, category_slug, brand_slug):
        res = self.client.get(CATEGORIES_URL)
        category = next(c for c in res.data if c["slug"] == category_slug)
        brand = next(b for b in category["brands"] if b["slug"] == brand_slug)
        return [sub["slug"] for sub in brand["sub"]]

    def test_each_tree_shows_only_its_own_sub_variants(self):
        self.assertEqual(self._sub_slugs("ongrid", "inverex"), ["inverex-ongrid-single"])
        self.assertEqual(self._sub_slugs("hybrid", "inverex"), ["inverex-hybrid-three"])

    def test_single_category_parent_needs_no_category_picked(self):
        sub = Brand.objects.create(name="Single Phase", slug="crown-single", parent=self.crown)

        self.assertEqual(sub.category, self.ongrid)

    def test_shared_parent_sub_variant_without_a_category_is_rejected(self):
        sub = Brand(name="Single Phase", slug="inverex-single", parent=self.inverex)

        with self.assertRaises(ValidationError) as ctx:
            sub.full_clean()

        message = ctx.exception.message_dict["category"][0]
        self.assertIn("Ongrid Inverters", message)
        self.assertIn("Hybrid Inverters", message)

    def test_category_the_parent_isnt_placed_in_is_rejected(self):
        sub = Brand(name="Single Phase", slug="crown-single", parent=self.crown, category=self.hybrid)

        with self.assertRaises(ValidationError) as ctx:
            sub.full_clean()

        self.assertIn("only placed in Ongrid Inverters", ctx.exception.message_dict["category"][0])

    def test_top_level_brand_cannot_carry_a_category(self):
        brand = Brand(name="Knox", slug="knox", category=self.ongrid)

        with self.assertRaises(ValidationError) as ctx:
            brand.full_clean()

        self.assertIn("Only a sub-variant", ctx.exception.message_dict["category"][0])

    def test_top_level_brand_category_is_cleared_on_save(self):
        brand = Brand.objects.create(name="Knox", slug="knox", category=self.ongrid)

        self.assertIsNone(brand.category)

    def test_sub_variant_without_a_category_still_shows_in_both_trees(self):
        # Transitional fallback for rows that predate the field.
        Brand.objects.filter(pk=self.hybrid_three.pk).update(category=None)

        self.assertIn("inverex-hybrid-three", self._sub_slugs("ongrid", "inverex"))
        self.assertIn("inverex-hybrid-three", self._sub_slugs("hybrid", "inverex"))

    def test_product_on_a_scoped_sub_variant_takes_its_category(self):
        product = Product.objects.create(
            brand=self.hybrid_three, name="Inverex 8kW", slug="inverex-8kw", price="180000.00"
        )

        # The sub-variant is already hybrid-only, so nothing is ambiguous even
        # though the parent brand sits under two categories.
        self.assertEqual(product.category, self.hybrid)


class BrandBackfillMigrationTests(APITestCase):
    """The 0009 backfill fills only the sub-variants the data decides on."""

    def setUp(self):
        self.ongrid = Category.objects.create(name="Ongrid Inverters", slug="ongrid", order=1)
        self.hybrid = Category.objects.create(name="Hybrid Inverters", slug="hybrid", order=2)

        self.inverex = Brand.objects.create(name="Inverex", slug="inverex")
        CategoryBrand.objects.create(category=self.ongrid, brand=self.inverex)
        CategoryBrand.objects.create(category=self.hybrid, brand=self.inverex)

        self.crown = Brand.objects.create(name="Crown", slug="crown")
        CategoryBrand.objects.create(category=self.ongrid, brand=self.crown)

        self.knox = Brand.objects.create(name="Knox", slug="knox")  # placed nowhere

        # Stand in for rows that predate the field.
        self.subs = {}
        for key, parent in [("inverex", self.inverex), ("crown", self.crown), ("knox", self.knox)]:
            sub = Brand.objects.create(name="Single Phase", slug=f"{key}-single", parent=parent)
            Brand.objects.filter(pk=sub.pk).update(category=None)
            self.subs[key] = sub

    def test_backfill(self):
        backfill_unambiguous_brand_categories(django_apps, None)

        for sub in self.subs.values():
            sub.refresh_from_db()

        self.assertEqual(self.subs["crown"].category, self.ongrid)  # one placement
        self.assertIsNone(self.subs["inverex"].category)  # two - admin picks
        self.assertIsNone(self.subs["knox"].category)  # none to fill

    def test_backfill_leaves_top_level_brands_alone(self):
        backfill_unambiguous_brand_categories(django_apps, None)
        self.crown.refresh_from_db()

        self.assertIsNone(self.crown.category)
