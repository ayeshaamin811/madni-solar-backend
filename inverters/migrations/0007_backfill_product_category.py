# 0006 added Product.category without touching existing rows. Every product
# created before it has the field unset, so fill in the ones whose answer is
# unambiguous: a brand placed under exactly one category leaves no choice.
#
# Products under a brand placed in two categories (Fox, Chint, Sofar, ... sit
# under both Ongrid and Hybrid) are deliberately left unset - nothing in the
# data says which tree they belong to, so an admin picks them by hand from the
# Products list, filtered on category's "-" bucket. Until then they keep
# showing under both categories, the same as before this field existed (see
# InverterProductListView).
from django.db import migrations


def backfill_unambiguous_categories(apps, schema_editor):
    Product = apps.get_model("inverters", "Product")
    CategoryBrand = apps.get_model("inverters", "CategoryBrand")

    # Category ids per top-level brand, in one pass - product counts are small
    # but this keeps the migration off a per-row query.
    categories_by_brand = {}
    for placement in CategoryBrand.objects.all():
        categories_by_brand.setdefault(placement.brand_id, set()).add(placement.category_id)

    for product in Product.objects.filter(category__isnull=True).select_related("brand"):
        # A product on a sub-variant takes its parent's placements - only
        # top-level brands carry CategoryBrand rows.
        node_id = product.brand.parent_id or product.brand_id
        category_ids = categories_by_brand.get(node_id, set())
        if len(category_ids) == 1:
            product.category_id = next(iter(category_ids))
            product.save(update_fields=["category"])


def clear_categories(apps, schema_editor):
    Product = apps.get_model("inverters", "Product")
    Product.objects.update(category=None)


class Migration(migrations.Migration):

    dependencies = [
        ("inverters", "0006_product_category"),
    ]

    operations = [
        migrations.RunPython(backfill_unambiguous_categories, clear_categories),
    ]
