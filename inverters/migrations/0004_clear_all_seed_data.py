# The full Category/Brand/CategoryBrand tree seeded by 0002 was only meant
# as a starting point. The admin wants to build the whole catalogue by hand
# instead (categories, brands, sub-variants, and products), so this clears
# everything the seed created, leaving all four tables empty.

from django.db import migrations


def clear_seed_data(apps, schema_editor):
    Category = apps.get_model("inverters", "Category")
    Brand = apps.get_model("inverters", "Brand")
    Category.objects.all().delete()  # cascades to CategoryBrand
    Brand.objects.all().delete()  # cascades to sub-variant Brands and Product


class Migration(migrations.Migration):

    dependencies = [
        ("inverters", "0003_delete_placeholder_products"),
    ]

    operations = [
        migrations.RunPython(clear_seed_data, migrations.RunPython.noop),
    ]
