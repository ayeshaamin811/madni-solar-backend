# Same shape as 0007, for the brand tree instead of products: 0008 added
# Brand.category without touching existing rows, so every sub-variant created
# before it has the field unset.
#
# Fill in the ones the data decides on its own - a sub-variant whose parent is
# placed under exactly one category has nowhere else to go. Sub-variants of a
# parent placed in two categories (Inverex sits under both Ongrid and Hybrid)
# are left unset for an admin to pick from the Brands list, filtered on
# category's "-" bucket; until then they keep showing under both, as before
# (see BrandNodeSerializer.get_sub).
from django.db import migrations


def backfill_unambiguous_categories(apps, schema_editor):
    Brand = apps.get_model("inverters", "Brand")
    CategoryBrand = apps.get_model("inverters", "CategoryBrand")

    categories_by_brand = {}
    for placement in CategoryBrand.objects.all():
        categories_by_brand.setdefault(placement.brand_id, set()).add(placement.category_id)

    for brand in Brand.objects.filter(category__isnull=True, parent__isnull=False):
        category_ids = categories_by_brand.get(brand.parent_id, set())
        if len(category_ids) == 1:
            brand.category_id = next(iter(category_ids))
            brand.save(update_fields=["category"])


def clear_categories(apps, schema_editor):
    Brand = apps.get_model("inverters", "Brand")
    Brand.objects.update(category=None)


class Migration(migrations.Migration):

    dependencies = [
        ("inverters", "0008_brand_category"),
    ]

    operations = [
        migrations.RunPython(backfill_unambiguous_categories, clear_categories),
    ]
