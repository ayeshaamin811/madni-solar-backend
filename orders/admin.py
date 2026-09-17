from django.contrib import admin

from .models import Order, OrderItem

# Everything the customer submitted. It is a record of what arrived, so there
# is no reason to allow editing it after the fact - `status` is the one field
# the sales team is meant to change, and it is deliberately absent from this
# list. Same convention as quotes.QuoteRequestAdmin.
SUBMITTED_FIELDS = (
    "order_number",
    "first_name",
    "last_name",
    "address",
    "apartment",
    "city",
    "state",
    "post_code",
    "country",
    "phone",
    "email",
    "business_name",
    "order_notes",
    "agreed_to_terms",
    "subtotal",
    "shipping",
    "total",
    "client_subtotal",
    "client_shipping",
    "client_total",
    "ip_address",
    "user_agent",
    "created_at",
)


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    # A snapshot of the basket at submit time, priced from the catalogue by
    # the serializer - editing a line here would misrepresent what was
    # ordered without changing the order total, which is stored separately.
    readonly_fields = ("name", "slug", "price", "quantity", "line_total", "source")
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        "order_number",
        "customer_name",
        "phone",
        "total",
        "status",
        "created_at",
    )
    list_filter = ("status", "created_at", "state")
    list_editable = ("status",)
    search_fields = ("order_number", "phone", "email")
    list_per_page = 50
    date_hierarchy = "created_at"
    inlines = [OrderItemInline]

    def get_readonly_fields(self, request, obj=None):
        # Everything is editable on the add form, otherwise it renders with no
        # inputs at all (Django shows readonly fields as plain text). On an
        # existing record the customer's own data stays readonly.
        if obj is None:
            return ()
        return SUBMITTED_FIELDS

    @admin.display(description="Customer", ordering="first_name")
    def customer_name(self, obj):
        return obj.customer_name
