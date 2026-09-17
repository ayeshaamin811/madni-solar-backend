from django.conf import settings
from django.db import models

# The checkout UI shows "Pakistan" as static text rather than a dropdown, so
# there is nothing to store per-order - it is the same for every customer.
COUNTRY = "Pakistan"

# The seven provinces/territories offered by the checkout dropdown. Kept as a
# module constant so the serializer and the model agree on one list.
STATE_CHOICES = [
    ("Punjab", "Punjab"),
    ("Sindh", "Sindh"),
    ("Khyber Pakhtunkhwa", "Khyber Pakhtunkhwa"),
    ("Balochistan", "Balochistan"),
    ("Azad Kashmir", "Azad Kashmir"),
    ("Gilgit-Baltistan", "Gilgit-Baltistan"),
    ("Islamabad Capital Territory", "Islamabad Capital Territory"),
]


class Order(models.Model):
    """A request to buy, not a paid transaction.

    There is no payment gateway in this project - the sales team confirms
    every order by phone, exactly like quotes.QuoteRequest. The difference is
    that an order carries a full billing address, a human-readable reference
    the customer can quote on the call, and a status the team works through.
    """

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        CONFIRMED = "confirmed", "Confirmed"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"

    # Human-readable reference (MS-<year>-<zero-padded id>). Assigned right
    # after the first save, since it needs the auto-increment id - hence
    # blank=True rather than a value supplied at construction time.
    order_number = models.CharField(max_length=32, unique=True, blank=True)

    # Billing details
    first_name = models.CharField(max_length=120)
    last_name = models.CharField(max_length=120)
    address = models.CharField(max_length=300)
    apartment = models.CharField(max_length=200, blank=True)
    city = models.CharField(max_length=120)
    state = models.CharField(max_length=60, choices=STATE_CHOICES, blank=True)
    post_code = models.CharField(max_length=20)
    country = models.CharField(max_length=60, default=COUNTRY)
    phone = models.CharField(max_length=32)
    email = models.EmailField()
    business_name = models.CharField(max_length=200, blank=True)
    order_notes = models.TextField(blank=True)
    agreed_to_terms = models.BooleanField(default=False)

    # Server-verified money. Every line is re-priced from the catalogue at
    # submit time (see orders/catalogue.py), so these are what the team
    # should quote on the phone - not whatever the browser sent.
    subtotal = models.DecimalField(max_digits=12, decimal_places=2)
    shipping = models.DecimalField(max_digits=12, decimal_places=2)
    total = models.DecimalField(max_digits=12, decimal_places=2)

    # What the browser claimed, kept as an audit trail. The serializer
    # rejects a submission whose total disagrees with the recomputed one, so
    # in practice these match the three fields above - they exist so that a
    # near-miss admitted by the rounding tolerance is still visible here, and
    # so the check can be relaxed later without losing the record.
    client_subtotal = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    client_shipping = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    client_total = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)

    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)

    # Kept for the same reason as quotes.QuoteRequest.ip_address/user_agent.
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=300, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["-created_at"]),
            models.Index(fields=["status"]),
        ]

    def __str__(self):
        return f"{self.order_number or 'MS-?'} - {self.first_name} {self.last_name}"

    def build_order_number(self):
        """MS-<year>-<zero-padded id>, e.g. MS-2026-0012.

        Derived from the id rather than a per-year counter: a counter would
        need its own row and a lock to stay gap-free under concurrent
        checkouts, and the customer only needs something unique they can read
        out over the phone.
        """
        return f"MS-{self.created_at.year}-{self.id:04d}"

    @property
    def customer_name(self):
        return f"{self.first_name} {self.last_name}"

    @property
    def currency(self):
        return settings.ORDER_CURRENCY


class OrderItem(models.Model):
    """One basket line, snapshotted at submit time.

    `name` and `price` are copied onto the row instead of pointing at a
    catalogue product: the price the customer saw has to survive a later
    catalogue edit, and there is no single FK target anyway since lines come
    from four separate apps (solar_panels, inverters, batteries, products).
    """

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    name = models.CharField(max_length=250)
    slug = models.SlugField(max_length=250)
    price = models.DecimalField(max_digits=12, decimal_places=2)
    quantity = models.PositiveIntegerField()
    line_total = models.DecimalField(max_digits=12, decimal_places=2)

    # Which catalogue the slug resolved against - handy in the admin when a
    # line needs chasing back to its source product.
    source = models.CharField(max_length=32, blank=True)

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return f"{self.name} x{self.quantity}"
