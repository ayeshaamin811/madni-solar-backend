import json
from decimal import Decimal

from rest_framework import serializers

from .models import CalculatorSubmission
from .utils import compress_bill_image

MAX_BILL_FILE_SIZE = 5 * 1024 * 1024  # 5 MB
ALLOWED_BILL_FILE_EXTENSIONS = {"jpg", "jpeg", "png", "webp", "pdf"}
IMAGE_BILL_FILE_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}

# Qty per appliance, sent as a JSON string in the "loads" field since the
# request is multipart/form-data.
LOAD_KEYS = (
    "ledBulbs",
    "tubeLights",
    "fans",
    "refrigerators",
    "ac1Ton",
    "ac1_5Ton",
    "ac2Ton",
    "ups1kw",
    "motor1hp",
)


class CalculatorSubmissionSerializer(serializers.ModelSerializer):
    meterType = serializers.ChoiceField(
        source="meter_type", choices=CalculatorSubmission.MeterType.choices
    )
    billAmount = serializers.DecimalField(
        source="bill_amount", max_digits=10, decimal_places=2, min_value=Decimal("0.01")
    )
    billUnits = serializers.DecimalField(
        source="bill_units", max_digits=10, decimal_places=2, min_value=Decimal("0.01")
    )
    billFile = serializers.FileField(source="bill_file", required=False, allow_null=True)
    fullName = serializers.CharField(source="full_name")
    houseArea = serializers.DecimalField(
        source="house_area", max_digits=8, decimal_places=2, min_value=Decimal("0.01")
    )
    loads = serializers.CharField()
    loadCalculated = serializers.DecimalField(
        source="load_calculated", max_digits=6, decimal_places=2, min_value=Decimal("0")
    )

    class Meta:
        model = CalculatorSubmission
        fields = [
            "id",
            "meterType",
            "billAmount",
            "billUnits",
            "billFile",
            "fullName",
            "phone",
            "email",
            "houseArea",
            "address",
            "loads",
            "loadCalculated",
        ]
        read_only_fields = ["id"]

    def validate_fullName(self, value):
        value = value.strip()
        if len(value) < 2:
            raise serializers.ValidationError("Please enter your full name.")
        return value

    def validate_phone(self, value):
        value = value.strip()
        if len(value) < 7:
            raise serializers.ValidationError("Please enter a valid phone number.")
        return value

    def validate_address(self, value):
        value = value.strip()
        if len(value) < 5:
            raise serializers.ValidationError("Please enter your full address.")
        return value

    def validate_billFile(self, value):
        if value is None:
            return value
        if value.size > MAX_BILL_FILE_SIZE:
            raise serializers.ValidationError("File is too large (max 5 MB).")
        extension = value.name.rsplit(".", 1)[-1].lower() if "." in value.name else ""
        if extension not in ALLOWED_BILL_FILE_EXTENSIONS:
            raise serializers.ValidationError(
                "Unsupported file type. Upload a JPG, PNG, WEBP image or a PDF."
            )

        if extension in IMAGE_BILL_FILE_EXTENSIONS:
            # Shrink phone-camera-sized photos before they ever reach disk or
            # an email attachment - see calculator/utils.py.
            try:
                return compress_bill_image(value)
            except ValueError:
                raise serializers.ValidationError(
                    "Could not process the uploaded image. Please try a different file."
                )
        return value

    def validate_loads(self, value):
        try:
            parsed = json.loads(value)
        except (TypeError, ValueError):
            raise serializers.ValidationError("Loads must be valid JSON.")

        if not isinstance(parsed, dict):
            raise serializers.ValidationError("Loads must be an object.")

        unknown_keys = set(parsed) - set(LOAD_KEYS)
        if unknown_keys:
            raise serializers.ValidationError(
                f"Unknown load key(s): {', '.join(sorted(unknown_keys))}."
            )

        cleaned = {}
        for key in LOAD_KEYS:
            qty = parsed.get(key, 0)
            if not isinstance(qty, int) or isinstance(qty, bool):
                raise serializers.ValidationError(f"'{key}' must be a whole number.")
            if qty < 0 or qty > 10:
                raise serializers.ValidationError(f"'{key}' must be between 0 and 10.")
            cleaned[key] = qty
        return cleaned
