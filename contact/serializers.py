from rest_framework import serializers

from .models import ContactMessage


class ContactMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContactMessage
        fields = ["id", "name", "email", "phone", "subject", "message"]
        read_only_fields = ["id"]

    def validate_name(self, value):
        value = value.strip()
        if len(value) < 2:
            raise serializers.ValidationError("Please enter your full name.")
        return value

    def validate_subject(self, value):
        value = value.strip()
        if len(value) < 3:
            raise serializers.ValidationError("Please enter a subject.")
        return value

    def validate_message(self, value):
        value = value.strip()
        if len(value) < 10:
            raise serializers.ValidationError("Please write a slightly longer message.")
        if len(value) > 5000:
            raise serializers.ValidationError("Message is too long (max 5000 characters).")
        return value

    def validate_phone(self, value):
        # Phone is optional and people write it in many different formats
        # (0300-1234567, +923001234567, 92 300 1234567). Deliberately lenient,
        # since strict rules here would reject real customers.
        return value.strip()

