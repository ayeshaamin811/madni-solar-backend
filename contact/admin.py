from django.contrib import admin
from django.utils import timezone

from .models import ContactMessage

# Data submitted by the customer. It is a record of what arrived, so there is
# no reason to allow editing it after the fact.
SUBMITTED_FIELDS = (
    "name",
    "email",
    "phone",
    "subject",
    "message",
    "ip_address",
    "user_agent",
    "created_at",
)


@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display = ("name", "email", "phone", "subject", "status", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("name", "email", "phone", "subject", "message")
    list_per_page = 50
    date_hierarchy = "created_at"
    actions = ["mark_replied", "mark_spam"]

    def get_readonly_fields(self, request, obj=None):
        # Everything is editable on the add form, otherwise it renders with no
        # inputs at all (Django shows readonly fields as plain text). On an
        # existing record the customer's own data stays readonly.
        if obj is None:
            return ()
        return SUBMITTED_FIELDS

    @admin.action(description="Mark as replied")
    def mark_replied(self, request, queryset):
        updated = queryset.update(
            status=ContactMessage.Status.REPLIED, replied_at=timezone.now()
        )
        self.message_user(request, f"{updated} message(s) marked as replied.")

    @admin.action(description="Mark as spam")
    def mark_spam(self, request, queryset):
        updated = queryset.update(status=ContactMessage.Status.SPAM)
        self.message_user(request, f"{updated} message(s) marked as spam.")
