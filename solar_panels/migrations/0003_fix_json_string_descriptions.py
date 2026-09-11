import json

from django.db import migrations


def convert_json_string_descriptions(apps, schema_editor):
    """One-time cleanup for products added while `description` was still a
    JSONField: their text column literally holds the old JSON-encoded array
    (e.g. '["Para one.", "Para two."]'). Re-parse that and rewrite it as
    plain text with a blank line between paragraphs, matching what
    ProductDetailSerializer.get_description() now expects.
    """
    Product = apps.get_model("solar_panels", "Product")
    for product in Product.objects.all():
        text = product.description
        if not text or not text.strip().startswith("["):
            continue
        try:
            paragraphs = json.loads(text)
        except (TypeError, ValueError):
            continue
        if not isinstance(paragraphs, list):
            continue
        product.description = "\n\n".join(str(p) for p in paragraphs)
        product.save(update_fields=["description"])


class Migration(migrations.Migration):

    dependencies = [
        ("solar_panels", "0002_alter_product_description"),
    ]

    operations = [
        migrations.RunPython(convert_json_string_descriptions, migrations.RunPython.noop),
    ]
