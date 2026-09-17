from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.db import transaction
from rest_framework import serializers

from .catalogue import resolve_slugs
from .models import STATE_CHOICES, Order, OrderItem

# Money arrives as JSON numbers, so a recomputed total can land a hair away
# from the browser's own arithmetic. Anything inside one paisa is treated as
# agreement; anything larger means the catalogue price actually moved.
MONEY_TOLERANCE = Decimal("0.01")
CENTS = Decimal("0.01")


def to_decimal(value):
    """JSON number (or string) -> Decimal, via str so float noise doesn't leak in."""
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None


class OrderItemSerializer(serializers.Serializer):
    """One basket line as the browser sent it.

    Only `slug` and `quantity` are load-bearing - `name`, `price` and
    `lineTotal` are accepted so the cart payload can be posted verbatim, but
    the stored values come from the catalogue lookup, not from here.
    """

    name = serializers.CharField(required=False, allow_blank=True)
    slug = serializers.CharField()
    price = serializers.FloatField(required=False, min_value=0)
    quantity = serializers.IntegerField(min_value=1)
    lineTotal = serializers.FloatField(required=False, min_value=0)

    def validate_slug(self, value):
        value = value.strip().lower()
        if not value:
            raise serializers.ValidationError("Item slug cannot be empty.")
        return value


class OrderSerializer(serializers.ModelSerializer):
    firstName = serializers.CharField(source="first_name")
    lastName = serializers.CharField(source="last_name")
    postCode = serializers.CharField(source="post_code")
    businessName = serializers.CharField(
        source="business_name", required=False, allow_blank=True
    )
    orderNotes = serializers.CharField(
        source="order_notes", required=False, allow_blank=True
    )
    agreedToTerms = serializers.BooleanField(source="agreed_to_terms")
    state = serializers.ChoiceField(
        choices=[value for value, _ in STATE_CHOICES], required=False, allow_blank=True
    )
    apartment = serializers.CharField(required=False, allow_blank=True)

    items = OrderItemSerializer(many=True, allow_empty=False)

    # The browser's own arithmetic. Mapped straight onto the client_* columns
    # so the authoritative subtotal/shipping/total can be recomputed in
    # create() without the two ever being confused for each other.
    subtotal = serializers.DecimalField(
        source="client_subtotal", max_digits=12, decimal_places=2, coerce_to_string=False
    )
    shipping = serializers.DecimalField(
        source="client_shipping", max_digits=12, decimal_places=2, coerce_to_string=False
    )
    total = serializers.DecimalField(
        source="client_total", max_digits=12, decimal_places=2, coerce_to_string=False
    )

    class Meta:
        model = Order
        fields = [
            "id",
            "firstName",
            "lastName",
            "address",
            "apartment",
            "city",
            "state",
            "postCode",
            "phone",
            "email",
            "businessName",
            "orderNotes",
            "agreedToTerms",
            "items",
            "subtotal",
            "shipping",
            "total",
        ]
        read_only_fields = ["id"]

    # --- field-level checks -------------------------------------------------

    def validate_firstName(self, value):
        value = value.strip()
        if len(value) < 2:
            raise serializers.ValidationError("Please enter your first name.")
        return value

    def validate_lastName(self, value):
        value = value.strip()
        if len(value) < 2:
            raise serializers.ValidationError("Please enter your last name.")
        return value

    def validate_address(self, value):
        value = value.strip()
        if len(value) < 5:
            raise serializers.ValidationError("Please enter your street address.")
        return value

    def validate_city(self, value):
        value = value.strip()
        if len(value) < 2:
            raise serializers.ValidationError("Please enter your town or city.")
        return value

    def validate_postCode(self, value):
        # Deliberately a string, not a number - a leading zero is part of the
        # code and an int would silently eat it.
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Please enter your postcode / ZIP.")
        return value

    def validate_phone(self, value):
        value = value.strip()
        if len(value) < 7:
            raise serializers.ValidationError("Please enter a valid phone number.")
        return value

    def validate_agreedToTerms(self, value):
        if not value:
            raise serializers.ValidationError(
                "Please accept the terms and conditions to place your order."
            )
        return value

    # --- cross-field checks -------------------------------------------------

    def validate(self, attrs):
        """Re-price every line from the catalogue and check the totals.

        `price` and the three totals come from the browser, where they can be
        edited, so nothing money-related is taken on trust. Lines are re-priced
        from the catalogue and the totals recomputed; a disagreement is a 400
        rather than a silently corrected order, because the customer needs to
        see the new price before committing to it.
        """
        lines = attrs.get("items") or []
        resolved = resolve_slugs(line["slug"] for line in lines)

        missing = [line["slug"] for line in lines if line["slug"] not in resolved]
        if missing:
            # A stale basket: the cart persists in localStorage under
            # `madniSolarCart` indefinitely, so any catalogue edit eventually
            # strands someone on a slug that no longer exists.
            joined = ", ".join(missing)
            raise serializers.ValidationError(
                {
                    "items": [
                        "These items are no longer available: "
                        + joined
                        + ". Please remove them from your basket."
                    ]
                }
            )

        priced = []
        subtotal = Decimal("0.00")
        for line in lines:
            entry = resolved[line["slug"]]
            quantity = line["quantity"]
            line_total = (entry.price * quantity).quantize(CENTS)
            subtotal += line_total
            priced.append(
                {
                    "name": entry.name,
                    "slug": entry.slug,
                    "price": entry.price.quantize(CENTS),
                    "quantity": quantity,
                    "line_total": line_total,
                    "source": entry.source,
                }
            )

        subtotal = subtotal.quantize(CENTS)
        shipping = to_decimal(settings.ORDER_FLAT_SHIPPING).quantize(CENTS)
        total = (subtotal + shipping).quantize(CENTS)

        client_total = attrs.get("client_total")
        if client_total is not None and abs(total - client_total) > MONEY_TOLERANCE:
            raise serializers.ValidationError(
                "Prices have changed since you added these items. "
                "Please refresh your basket."
            )

        attrs["items"] = priced
        attrs["subtotal"] = subtotal
        attrs["shipping"] = shipping
        attrs["total"] = total
        return attrs

    # --- persistence --------------------------------------------------------

    @transaction.atomic
    def create(self, validated_data):
        lines = validated_data.pop("items")
        order = Order.objects.create(**validated_data)

        # Needs the auto-increment id, so it can only be built after the
        # first save (see Order.build_order_number).
        order.order_number = order.build_order_number()
        order.save(update_fields=["order_number"])

        OrderItem.objects.bulk_create(
            OrderItem(order=order, **line) for line in lines
        )
        return order
