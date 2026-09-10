from django.conf import settings
from django.core import mail
from django.core.cache import cache
from rest_framework.test import APITestCase

from .models import ContactMessage

URL = "/api/contact/"

PAYLOAD = {
    "name": "Ali Raza",
    "email": "ali@example.com",
    "phone": "+92 300 1234567",
    "subject": "Quote chahiye",
    "message": "10kW system ke liye rate bata dein.",
}


class ContactAPITests(APITestCase):
    def setUp(self):
        # Throttle counters live in the cache, so start each test from clean.
        cache.clear()

    def test_creates_message_and_sends_email(self):
        res = self.client.post(URL, PAYLOAD, format="json")

        self.assertEqual(res.status_code, 201)
        self.assertEqual(ContactMessage.objects.count(), 1)
        # One notification to the team, one auto-reply to the customer.
        self.assertEqual(len(mail.outbox), 2)

        msg = ContactMessage.objects.get()
        self.assertEqual(msg.name, "Ali Raza")
        self.assertEqual(msg.status, ContactMessage.Status.NEW)
        self.assertEqual(res.data["id"], msg.id)
        self.assertIn("Thank you", res.data["message"])

    def test_team_notification_has_customer_reply_to(self):
        self.client.post(URL, PAYLOAD, format="json")

        team_email = mail.outbox[0]
        self.assertEqual(team_email.to, settings.CONTACT_NOTIFY_EMAILS)
        self.assertEqual(team_email.reply_to, ["ali@example.com"])
        self.assertIn("Quote chahiye", team_email.subject)
        # Sent as HTML with a plain-text fallback.
        self.assertEqual(len(team_email.alternatives), 1)
        self.assertEqual(team_email.alternatives[0][1], "text/html")

    def test_customer_gets_confirmation_email(self):
        self.client.post(URL, PAYLOAD, format="json")

        customer_email = mail.outbox[1]
        self.assertEqual(customer_email.to, ["ali@example.com"])
        self.assertIn("Madni Solar", customer_email.subject)
        self.assertEqual(len(customer_email.alternatives), 1)
        self.assertEqual(customer_email.alternatives[0][1], "text/html")
        self.assertIn("Ali Raza", customer_email.body)

    def test_records_ip_and_user_agent(self):
        res = self.client.post(
            URL,
            PAYLOAD,
            format="json",
            HTTP_X_FORWARDED_FOR="203.0.113.9, 10.0.0.1",
            HTTP_USER_AGENT="Mozilla/5.0 (test)",
        )

        self.assertEqual(res.status_code, 201)
        msg = ContactMessage.objects.get()
        self.assertEqual(msg.ip_address, "203.0.113.9")
        self.assertEqual(msg.user_agent, "Mozilla/5.0 (test)")

    def test_rejects_invalid_email(self):
        res = self.client.post(URL, {**PAYLOAD, "email": "nope"}, format="json")

        self.assertEqual(res.status_code, 400)
        self.assertIn("email", res.data)
        self.assertEqual(ContactMessage.objects.count(), 0)

    def test_rejects_short_message(self):
        res = self.client.post(URL, {**PAYLOAD, "message": "hi"}, format="json")

        self.assertEqual(res.status_code, 400)
        self.assertIn("message", res.data)

    def test_rejects_missing_required_fields(self):
        res = self.client.post(URL, {"phone": "0300"}, format="json")

        self.assertEqual(res.status_code, 400)
        for field in ("name", "email", "subject", "message"):
            self.assertIn(field, res.data)

    def test_phone_is_optional(self):
        payload = {**PAYLOAD}
        payload.pop("phone")

        res = self.client.post(URL, payload, format="json")

        self.assertEqual(res.status_code, 201)
        self.assertEqual(ContactMessage.objects.get().phone, "")

    def test_unknown_fields_are_ignored(self):
        # An old cached front-end build might still send a stray field (e.g.
        # a removed honeypot). The serializer should just ignore it rather
        # than error, so a stale client keeps working.
        res = self.client.post(URL, {**PAYLOAD, "hp_note": "leftover"}, format="json")

        self.assertEqual(res.status_code, 201)
        self.assertEqual(ContactMessage.objects.count(), 1)

    def test_throttles_after_five_messages(self):
        for i in range(5):
            res = self.client.post(URL, PAYLOAD, format="json")
            self.assertEqual(res.status_code, 201, f"request {i + 1} should pass")

        res = self.client.post(URL, PAYLOAD, format="json")
        self.assertEqual(res.status_code, 429)
        self.assertIn("detail", res.data)
        self.assertEqual(ContactMessage.objects.count(), 5)

    def test_no_auth_required(self):
        # The endpoint is public: no credentials, and no CSRF problems either.
        res = self.client.post(URL, PAYLOAD, format="json")
        self.assertEqual(res.status_code, 201)
