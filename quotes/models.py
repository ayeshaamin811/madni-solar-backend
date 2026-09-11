from django.db import models


class QuoteRequest(models.Model):
    first_name = models.CharField(max_length=120)
    last_name = models.CharField(max_length=120)
    phone = models.CharField(max_length=32)
    email = models.EmailField(blank=True)
    message = models.TextField(blank=True)

    # Plain snapshot of what the customer saw on the page at submit time -
    # not looked up against a product catalog (three of the four catalogue
    # types aren't backed by Django models yet). Same reasoning as
    # calculator.CalculatorSubmission.loads.
    items = models.JSONField(default=list, blank=True)
    quote_total = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

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
        return f"{self.first_name} {self.last_name} ({len(self.items)} item(s))"
