from django.core import mail
from django.core.cache import cache
from rest_framework.test import APITestCase

from .models import QuoteRequest

URL = "/api/quotes/"

ITEMS = [
    {
        "name": "Yingli Solar 550W Mono Panel",
        "slug": "yingli-solar-550w-mono-panel",
        "price": 18500,
        "quantity": 1,
        "lineTotal": 18500,
    },
    {
        "name": "Astronergy 620W N-Type Bifacial Solar Panel",
        "slug": "astronergy-620w-n-type-bifacial-solar-panel",
        "price": 22000,
        "quantity": 2,
        "lineTotal": 44000,
    },
]

PAYLOAD = {
    "firstName": "Ali",
    "lastName": "Raza",
    "phone": "+92 300 1234567",
    "email": "ali@example.com",
    "message": "Please call before delivery.",
    "items": ITEMS,
    "quoteTotal": 62500,
}


class QuoteAPITests(APITestCase):
    def setUp(self):
        # Throttle counters live in the cache, so start each test from clean.
        cache.clear()

    def test_creates_quote_and_sends_emails(self):
        res = self.client.post(URL, PAYLOAD, format="json")

        self.assertEqual(res.status_code, 201)
        self.assertEqual(QuoteRequest.objects.count(), 1)

        quote = QuoteRequest.objects.get()
        self.assertEqual(quote.first_name, "Ali")
        self.assertEqual(quote.last_name, "Raza")
        self.assertEqual(len(quote.items), 2)
        self.assertEqual(quote.items[0]["name"], "Yingli Solar 550W Mono Panel")
        self.assertEqual(float(quote.quote_total), 62500.0)
        self.assertEqual(res.data["id"], quote.id)
        self.assertIn("Thank you", res.data["message"])

        # Team notification + customer confirmation (customer gave an email).
        self.assertEqual(len(mail.outbox), 2)

    def test_records_ip_and_user_agent(self):
        res = self.client.post(
            URL,
            PAYLOAD,
            format="json",
            HTTP_X_FORWARDED_FOR="203.0.113.9, 10.0.0.1",
            HTTP_USER_AGENT="Mozilla/5.0 (test)",
        )

        self.assertEqual(res.status_code, 201)
        quote = QuoteRequest.objects.get()
        self.assertEqual(quote.ip_address, "203.0.113.9")
        self.assertEqual(quote.user_agent, "Mozilla/5.0 (test)")

    def test_items_can_be_empty_for_a_general_enquiry(self):
        payload = {**PAYLOAD, "items": [], "quoteTotal": None}
        res = self.client.post(URL, payload, format="json")

        self.assertEqual(res.status_code, 201)
        self.assertEqual(QuoteRequest.objects.get().items, [])

    def test_items_field_is_optional(self):
        payload = {k: v for k, v in PAYLOAD.items() if k not in ("items", "quoteTotal")}
        res = self.client.post(URL, payload, format="json")

        self.assertEqual(res.status_code, 201)
        self.assertEqual(QuoteRequest.objects.get().items, [])

    def test_email_is_optional(self):
        payload = {k: v for k, v in PAYLOAD.items() if k != "email"}
        res = self.client.post(URL, payload, format="json")

        self.assertEqual(res.status_code, 201)
        self.assertEqual(QuoteRequest.objects.get().email, "")
        # No customer address -> only the team notification goes out.
        self.assertEqual(len(mail.outbox), 1)

    def test_rejects_invalid_email_when_present(self):
        res = self.client.post(URL, {**PAYLOAD, "email": "nope"}, format="json")

        self.assertEqual(res.status_code, 400)
        self.assertIn("email", res.data)
        self.assertEqual(QuoteRequest.objects.count(), 0)

    def test_rejects_short_first_name(self):
        res = self.client.post(URL, {**PAYLOAD, "firstName": "A"}, format="json")

        self.assertEqual(res.status_code, 400)
        self.assertIn("firstName", res.data)

    def test_rejects_short_phone(self):
        res = self.client.post(URL, {**PAYLOAD, "phone": "030"}, format="json")

        self.assertEqual(res.status_code, 400)
        self.assertIn("phone", res.data)

    def test_rejects_missing_required_fields(self):
        res = self.client.post(URL, {}, format="json")

        self.assertEqual(res.status_code, 400)
        for field in ("firstName", "lastName", "phone"):
            self.assertIn(field, res.data)

    def test_rejects_item_without_a_name(self):
        bad_items = [{"slug": "no-name", "price": 100, "quantity": 1, "lineTotal": 100}]
        res = self.client.post(URL, {**PAYLOAD, "items": bad_items}, format="json")

        self.assertEqual(res.status_code, 400)
        self.assertIn("items", res.data)
        self.assertEqual(QuoteRequest.objects.count(), 0)

    def test_rejects_negative_quantity(self):
        bad_items = [{"name": "Bad Item", "price": 100, "quantity": -1, "lineTotal": -100}]
        res = self.client.post(URL, {**PAYLOAD, "items": bad_items}, format="json")

        self.assertEqual(res.status_code, 400)
        self.assertIn("items", res.data)

    def test_team_notification_has_customer_reply_to(self):
        self.client.post(URL, PAYLOAD, format="json")

        team_email = mail.outbox[0]
        self.assertEqual(team_email.reply_to, ["ali@example.com"])
        self.assertIn("Ali Raza", team_email.subject)
        self.assertEqual(len(team_email.alternatives), 1)
        self.assertEqual(team_email.alternatives[0][1], "text/html")

    def test_customer_gets_confirmation_email(self):
        self.client.post(URL, PAYLOAD, format="json")

        customer_email = mail.outbox[1]
        self.assertEqual(customer_email.to, ["ali@example.com"])
        self.assertIn("Madni Solar", customer_email.subject)
        self.assertIn("Ali", customer_email.body)

    def test_throttles_after_five_submissions(self):
        for i in range(5):
            res = self.client.post(URL, PAYLOAD, format="json")
            self.assertEqual(res.status_code, 201, f"request {i + 1} should pass")

        res = self.client.post(URL, PAYLOAD, format="json")
        self.assertEqual(res.status_code, 429)
        self.assertIn("detail", res.data)
        self.assertEqual(QuoteRequest.objects.count(), 5)

    def test_no_auth_required(self):
        res = self.client.post(URL, PAYLOAD, format="json")
        self.assertEqual(res.status_code, 201)
