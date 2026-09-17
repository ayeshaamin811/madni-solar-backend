"""Resolve a basket line's `slug` back to the product it came from.

Product slugs are globally unique across all four catalogues by design -
batteries prefix theirs with `battery-` and accessories with their category
slug, precisely so a Huawei package, a Huawei battery and a Huawei inverter
can't collide when the cart only stores a slug.

Lookup is a direct model query per app (four queries total, whatever the
basket size), not four HTTP round-trips against the public detail endpoints.
"""
from dataclasses import dataclass
from decimal import Decimal

from batteries.models import Product as BatteryProduct
from inverters.models import Product as InverterProduct
from products.models import Product as AccessoryProduct
from solar_panels.models import Product as SolarPanelProduct

# (source label, model). The label is stored on OrderItem.source so the admin
# can tell which catalogue a line came from.
CATALOGUES = (
    ("solar_panels", SolarPanelProduct),
    ("inverters", InverterProduct),
    ("batteries", BatteryProduct),
    ("products", AccessoryProduct),
)


@dataclass(frozen=True)
class CatalogueEntry:
    slug: str
    name: str
    price: Decimal
    source: str
    image_url: str = ""


def resolve_slugs(slugs):
    """Map each slug that exists in any catalogue to a CatalogueEntry.

    Slugs that match nothing are simply absent from the returned dict - the
    caller decides what to do about them (the order serializer turns them
    into a field error naming the offending slug).

    Catalogues are searched in CATALOGUES order; since slugs are unique
    across all four, the order only matters if that invariant is ever broken
    by a hand-edited slug, in which case the first match wins.
    """
    wanted = {s for s in slugs if s}
    if not wanted:
        return {}

    resolved = {}
    for source, model in CATALOGUES:
        remaining = wanted - resolved.keys()
        if not remaining:
            break

        rows = model.objects.filter(slug__in=remaining).only("slug", "name", "price", "image")
        for product in rows:
            resolved[product.slug] = CatalogueEntry(
                slug=product.slug,
                name=product.name,
                price=product.price,
                source=source,
                # The cart's own `image` is a bundled frontend asset URL and
                # is deliberately ignored; this is the real catalogue photo.
                image_url=product.image.url if product.image else "",
            )

    return resolved
