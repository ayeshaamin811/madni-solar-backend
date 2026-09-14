# The Product rows created by 0002_seed_inverter_tree.py were only ever
# generic placeholders (name/price/description templated from the brand
# name). Real products get added per brand/sub-variant through the admin
# instead - this migration clears just those placeholder rows so a fresh
# "Add Product" is empty per brand. The Category/Brand/CategoryBrand tree
# (the menu structure) is untouched.

from django.db import migrations


def delete_placeholder_products(apps, schema_editor):
    Product = apps.get_model("inverters", "Product")
    Product.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ("inverters", "0002_seed_inverter_tree"),
    ]

    operations = [
        migrations.RunPython(delete_placeholder_products, migrations.RunPython.noop),
    ]
