# Seeds the fixed category/brand/sub-variant navigation tree that used to
# live in the frontend's static src/data/inverterMenu.js, so a fresh
# deploy (Railway included) has the full mega-menu structure and a
# placeholder product per leaf ready for the admin to fill in with real
# copy/pricing/photos - see the "Inverters API" task spec for the source
# tree and the slug-collision decisions baked in below.
#
# A brand name that's flat (no sub-variants) in every category it appears
# in (Fox, Sofar, Sineng, Growatt, Huawei, Chint, MaxPower, Luminey, Crown,
# ZIEWNIC) is ONE shared Brand row placed under each category via
# CategoryBrand, with a single shared Product. A brand name whose shape
# differs by category (Inverex, Goodwe, Knox, Solis have sub-variants in
# one category and are flat in the other) becomes two distinct Brand rows
# with disambiguated slugs - the sub-variant-bearing one keeps the bare
# name as its slug, the flat one gets a `-ongrid`/`-hybrid` suffix.

from django.db import migrations

CATEGORIES = [
    {
        "name": "Ongrid Inverters",
        "slug": "ongrid-inverters",
        "order": 0,
        "description": (
            "Ongrid (grid-tie) inverters convert the DC power from your solar panels into AC and "
            "sync it directly with the WAPDA grid, letting you offset your bill through net metering. "
            "They're the most common choice for homes and businesses that stay connected to the grid."
        ),
        "brands": [
            {"name": "Canadian", "slug": "canadian"},
            {"name": "Fox", "slug": "fox"},
            {"name": "SolarMax", "slug": "solarmax"},
            {"name": "Sofar", "slug": "sofar"},
            {"name": "Goodwe", "slug": "goodwe-ongrid"},
            {"name": "Sineng", "slug": "sineng"},
            {"name": "Growatt", "slug": "growatt"},
            {"name": "Huawei", "slug": "huawei"},
            {
                "name": "Inverex",
                "slug": "inverex",
                "sub": [
                    {"name": "Single Phase", "slug": "inverex-single-phase"},
                    {"name": "Three Phase", "slug": "inverex-three-phase"},
                ],
            },
            {"name": "Knox", "slug": "knox-ongrid"},
            {"name": "SMA", "slug": "sma"},
            {"name": "Chint", "slug": "chint"},
            {"name": "MaxPower", "slug": "maxpower"},
            {"name": "Livoltek", "slug": "livoltek"},
            {"name": "Luminey", "slug": "luminey"},
            {"name": "Solis", "slug": "solis-ongrid"},
            {"name": "Sungrow", "slug": "sungrow"},
            {"name": "ZIEWNIC", "slug": "ziewnic"},
            {"name": "Crown", "slug": "crown"},
        ],
    },
    {
        "name": "Batteryless PV Inverters",
        "slug": "batteryless-pv-inverters",
        "order": 1,
        "description": (
            "Batteryless PV inverters run your solar array without a battery bank, sending power "
            "straight to your loads and the grid - a simpler, lower-cost setup for sites that don't "
            "need backup power during outages."
        ),
        "brands": [
            {"name": "Fronus", "slug": "fronus"},
            {"name": "Ziewnic", "slug": "ziewnic"},
        ],
    },
    {
        "name": "Hybrid Inverters",
        "slug": "hybrid-inverters",
        "order": 2,
        "description": (
            "Hybrid inverters combine solar charging, battery storage, and grid-tie in a single unit, "
            "so your system can store excess solar power and keep running through a grid outage."
        ),
        "brands": [
            {"name": "Chint", "slug": "chint"},
            {"name": "Sineng", "slug": "sineng"},
            {"name": "Sofar", "slug": "sofar"},
            {
                "name": "Hoymiles",
                "slug": "hoymiles",
                "sub": [
                    {"name": "Single Phase", "slug": "hoymiles-single-phase"},
                    {"name": "Three Phase", "slug": "hoymiles-three-phase"},
                ],
            },
            {"name": "Auxsol", "slug": "auxsol"},
            {"name": "Fox", "slug": "fox"},
            {
                "name": "Goodwe",
                "slug": "goodwe",
                "sub": [
                    {"name": "Single Phase", "slug": "goodwe-single-phase"},
                    {"name": "Three Phase LV", "slug": "goodwe-three-phase-lv"},
                    {"name": "Three Phase HV", "slug": "goodwe-three-phase-hv"},
                ],
            },
            {"name": "Growatt", "slug": "growatt"},
            {"name": "Inverex", "slug": "inverex-hybrid"},
            {"name": "Anicsun", "slug": "anicsun"},
            {"name": "MaxPower", "slug": "maxpower"},
            {"name": "Pilot", "slug": "pilot"},
            {"name": "Luminey", "slug": "luminey"},
            {"name": "Crown", "slug": "crown"},
            {"name": "Solar Max", "slug": "solar-max"},
            {
                "name": "Solis",
                "slug": "solis",
                "sub": [
                    {"name": "Single Phase", "slug": "solis-single-phase"},
                    {"name": "Three Phase", "slug": "solis-three-phase"},
                ],
            },
            {"name": "Itel", "slug": "itel"},
            {"name": "Huawei", "slug": "huawei"},
            {"name": "ZIEWNIC", "slug": "ziewnic"},
            {
                "name": "Knox",
                "slug": "knox",
                "sub": [
                    {"name": "Krypton", "slug": "knox-krypton"},
                    {"name": "XENON", "slug": "knox-xenon"},
                    {"name": "Zapher", "slug": "knox-zapher"},
                    {"name": "Zynex", "slug": "knox-zynex"},
                ],
            },
            {
                "name": "SAJ",
                "slug": "saj",
                "sub": [
                    {"name": "Single Phase", "slug": "saj-single-phase"},
                    {"name": "Three Phase", "slug": "saj-three-phase"},
                ],
            },
        ],
    },
]

PLACEHOLDER_PRICE = "150000.00"


def _placeholder_product_fields(display_name, backer_name):
    product_name = f"{display_name} Solar Inverter"
    return {
        "name": product_name,
        "slug": None,  # filled in by the caller, same as the brand/sub-variant slug
        "price": PLACEHOLDER_PRICE,
        "short_description": (
            f"The {product_name} is a placeholder product description. Replace it with real "
            "specifications, pricing, and photos once available."
        ),
        "description": (
            f"The {product_name} is engineered to deliver dependable performance for its intended "
            "installation type, converting DC power from solar panels into usable AC output with "
            "high efficiency.\n\n"
            "Placeholder specifications are shown here until real technical details, certifications, "
            "and pricing are added for this model."
        ),
        "why_choose": (
            f"Reliable performance backed by {backer_name}\n"
            "Efficient DC-to-AC conversion for lower running costs\n"
            "Straightforward installation and maintenance\n"
            "Placeholder pricing - contact us for a current quote"
        ),
    }


def seed_inverters(apps, schema_editor):
    Category = apps.get_model("inverters", "Category")
    Brand = apps.get_model("inverters", "Brand")
    CategoryBrand = apps.get_model("inverters", "CategoryBrand")
    Product = apps.get_model("inverters", "Product")

    brands_by_slug = {}

    for category_data in CATEGORIES:
        category = Category.objects.create(
            name=category_data["name"],
            slug=category_data["slug"],
            description=category_data["description"],
            order=category_data["order"],
        )

        for brand_order, brand_data in enumerate(category_data["brands"]):
            brand = brands_by_slug.get(brand_data["slug"])
            if brand is None:
                brand = Brand.objects.create(
                    name=brand_data["name"],
                    slug=brand_data["slug"],
                )
                brands_by_slug[brand_data["slug"]] = brand

                sub_variants = brand_data.get("sub", [])
                if sub_variants:
                    for sub_order, sub_data in enumerate(sub_variants):
                        sub_brand = Brand.objects.create(
                            parent=brand,
                            name=sub_data["name"],
                            slug=sub_data["slug"],
                            order=sub_order,
                        )
                        display_name = f"{brand.name} {sub_data['name']}"
                        fields = _placeholder_product_fields(display_name, brand.name)
                        fields["slug"] = sub_data["slug"]
                        Product.objects.create(brand=sub_brand, **fields)
                else:
                    fields = _placeholder_product_fields(brand.name, brand.name)
                    fields["slug"] = brand.slug
                    Product.objects.create(brand=brand, **fields)

            CategoryBrand.objects.create(category=category, brand=brand, order=brand_order)


def unseed_inverters(apps, schema_editor):
    Category = apps.get_model("inverters", "Category")
    Category.objects.all().delete()  # cascades to CategoryBrand
    Brand = apps.get_model("inverters", "Brand")
    Brand.objects.all().delete()  # cascades to Product and sub-variant Brands


class Migration(migrations.Migration):

    dependencies = [
        ("inverters", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed_inverters, unseed_inverters),
    ]
