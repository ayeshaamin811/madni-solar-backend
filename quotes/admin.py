from django.contrib import admin

from .models import QuoteRequest

# Data submitted by the customer. It is a record of what arrived, so there is
# no reason to allow editing it after the fact.
SUBMITTED_FIELDS = (
    "first_name",
    "last_name",
    "phone",
    "email",
    "message",
    "items",
    "quote_total",
    "ip_address",
    "user_agent",
    "created_at",
)


@admin.register(QuoteRequest)
class QuoteRequestAdmin(admin.ModelAdmin):
    list_display = ("first_name", "last_name", "phone", "email", "item_count", "quote_total", "created_at")
    search_fields = ("first_name", "last_name", "phone", "email")
    list_per_page = 50
    date_hierarchy = "created_at"

    def get_readonly_fields(self, request, obj=None):
        # Everything is editable on the add form, otherwise it renders with no
        # inputs at all (Django shows readonly fields as plain text). On an
        # existing record the customer's own data stays readonly.
        if obj is None:
            return ()
        return SUBMITTED_FIELDS

    def item_count(self, obj):
        return len(obj.items)

    item_count.short_description = "Items"
