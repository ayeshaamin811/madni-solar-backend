from rest_framework import serializers

from .models import QuoteRequest


class QuoteItemSerializer(serializers.Serializer):
    """One line item exactly as the customer saw it on the page - plain
    data, not looked up against a product model (see models.py)."""

    name = serializers.CharField()
    slug = serializers.CharField(required=False, allow_blank=True)
    price = serializers.FloatField(required=False, min_value=0)
    quantity = serializers.IntegerField(required=False, min_value=1)
    lineTotal = serializers.FloatField(required=False, min_value=0)

    def validate_name(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Item name cannot be empty.")
        return value


class QuoteRequestSerializer(serializers.ModelSerializer):
    firstName = serializers.CharField(source="first_name")
    lastName = serializers.CharField(source="last_name")
    items = QuoteItemSerializer(many=True, required=False)
    quoteTotal = serializers.DecimalField(
        source="quote_total",
        max_digits=10,
        decimal_places=2,
        required=False,
        allow_null=True,
        coerce_to_string=False,
    )

    class Meta:
        model = QuoteRequest
        fields = ["id", "firstName", "lastName", "phone", "email", "message", "items", "quoteTotal"]
        read_only_fields = ["id"]

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

    def validate_phone(self, value):
        value = value.strip()
        if len(value) < 7:
            raise serializers.ValidationError("Please enter a valid phone number.")
        return value
