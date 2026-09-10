from django.contrib import admin
from django.utils.html import format_html

from .models import CalculatorSubmission

IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp")

# Data submitted by the customer. It is a record of what arrived, so there is
# no reason to allow editing it after the fact.
SUBMITTED_FIELDS = (
    "meter_type",
    "bill_amount",
    "bill_units",
    "bill_file",
    "full_name",
    "phone",
    "email",
    "house_area",
    "address",
    "loads",
    "load_calculated",
    "ip_address",
    "user_agent",
    "created_at",
)


@admin.register(CalculatorSubmission)
class CalculatorSubmissionAdmin(admin.ModelAdmin):
    list_display = (
        "full_name",
        "phone",
        "meter_type",
        "bill_amount",
        "bill_units",
        "load_calculated",
        "created_at",
    )
    list_filter = ("meter_type", "created_at")
    search_fields = ("full_name", "phone", "email", "address")
    list_per_page = 50
    date_hierarchy = "created_at"

    def get_readonly_fields(self, request, obj=None):
        # Everything is editable on the add form, otherwise it renders with no
        # inputs at all (Django shows readonly fields as plain text). On an
        # existing record the customer's own data stays readonly.
        if obj is None:
            return ()
        return SUBMITTED_FIELDS + ("bill_file_preview",)

    def bill_file_preview(self, obj):
        if not obj or not obj.bill_file:
            return "-"
        if obj.bill_file.name.lower().endswith(IMAGE_EXTENSIONS):
            return format_html(
                '<img src="{}" style="max-width:420px; max-height:420px; '
                'border-radius:6px; border:1px solid #ddd;">',
                obj.bill_file.url,
            )
        return format_html('<a href="{}" target="_blank">View PDF</a>', obj.bill_file.url)

    bill_file_preview.short_description = "Bill Preview"
