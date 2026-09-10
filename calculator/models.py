from django.db import models


class CalculatorSubmission(models.Model):
    class MeterType(models.TextChoices):
        SINGLE = "single", "Single Phase"
        THREE = "three", "Three Phase"

    meter_type = models.CharField(max_length=10, choices=MeterType.choices)
    bill_amount = models.DecimalField(max_digits=10, decimal_places=2)
    bill_units = models.DecimalField(max_digits=10, decimal_places=2)
    bill_file = models.FileField(upload_to="calculator/bills/%Y/%m/", null=True, blank=True)

    full_name = models.CharField(max_length=120)
    phone = models.CharField(max_length=32)
    email = models.EmailField()
    house_area = models.DecimalField(max_digits=8, decimal_places=2)
    address = models.TextField()

    # Per-appliance quantities keyed by the frontend's camelCase names (e.g.
    # "ledBulbs", "ac1_5Ton") - stored as submitted so admin can see exactly
    # what the customer picked.
    loads = models.JSONField(default=dict)
    load_calculated = models.DecimalField(max_digits=6, decimal_places=2)

    # Kept for the same reason as ContactMessage.ip_address/user_agent.
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=300, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["-created_at"]),
        ]

    def __str__(self):
        return f"{self.full_name} - {self.get_meter_type_display()}"
