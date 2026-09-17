from decimal import Decimal

from django.core import mail
from django.core.cache import cache
from rest_framework.test import APITestCase

from batteries.models import Brand as BatteryBrand
from batteries.models import Product as BatteryProduct
from inverters.models import Brand as InverterBrand
from inverters.models import Product as InverterProduct
from solar_panels.models import Brand as PanelBrand
from solar_panels.models import Product as PanelProduct

from .models import Order, OrderItem

URL = "/api/orders/"
SETTINGS_URL = "/api/orders/settings/"

SHIPPING = 2000


def billing(**overrides):
    payload = {
        "firstName": "Ali",
        "lastName": "Raza",
        "address": "House 12, Street 5, Model Town",
        "apartment": "Flat 3B",
        "city": "Lahore",
        "state": "Punjab",
        "postCode": "05400",
        "phone": "+92 300 1234567",
        "email": "ali@example.com",
        "businessName": "Raza Traders",
        "orderNotes": "Please call before delivery.",
        "agreedToTerms": True,
    }
    payload.update(overrides)
    return payload


class OrderAPITests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        panel_brand = PanelBrand.objects.create(name="Yingli", slug="yingli")
        cls.panel = PanelProduct.objects.create(
            brand=panel_brand,
            name="Yingli Solar 550W Mono Panel",
            slug="yingli-solar-550w-mono-panel",
            price=Decimal("18500.00"),
        )

        inverter_brand = InverterBrand.objects.create(name="Inverex", slug="inverex")
        cls.inverter = InverterProduct.objects.create(
            brand=inverter_brand,
            name="Inverex Nitrox 6KW",
            slug="inverex-nitrox-6kw",
            price=Decimal("185000.00"),
        )

        battery_brand = BatteryBrand.objects.create(name="Huawei", slug="huawei-battery-brand")
        cls.battery = BatteryProduct.objects.create(
            brand=battery_brand,
            name="Huawei LUNA2000",
            slug="battery-huawei-luna2000",
            price=Decimal("500000.00"),
        )

    def setUp(self):
        # Throttle counters live in the cache, so start each test from clean.
        cache.clear()

    def payload(self, items=None, **overrides):
        items = items if items is not None else [
            {
                "name": self.panel.name,
                "slug": self.panel.slug,
                "price": 18500,
                "quantity": 2,
                "lineTotal": 37000,
            }
        ]
        subtotal = sum(item["lineTotal"] for item in items)
        data = billing(**overrides)
        data.update(
            {
                "items": items,
                "subtotal": subtotal,
                "shipping": SHIPPING,
                "total": subtotal + SHIPPING,
            }
        )
        return data

    # --- happy path ---------------------------------------------------------

    def test_creates_order_with_items_and_sends_emails(self):
        res = self.client.post(URL, self.payload(), format="json")

        self.assertEqual(res.status_code, 201)
        self.assertEqual(Order.objects.count(), 1)

        order = Order.objects.get()
        self.assertEqual(order.first_name, "Ali")
        self.assertEqual(order.post_code, "05400")
        self.assertEqual(order.country, "Pakistan")
        self.assertEqual(order.status, Order.Status.PENDING)
        self.assertEqual(order.total, Decimal("39000.00"))

        self.assertEqual(order.items.count(), 1)
        line = order.items.get()
        self.assertEqual(line.slug, self.panel.slug)
        self.assertEqual(line.quantity, 2)
        self.assertEqual(line.line_total, Decimal("37000.00"))
        self.assertEqual(line.source, "solar_panels")

        self.assertEqual(res.data["id"], order.id)
        self.assertEqual(res.data["orderNumber"], order.order_number)
        self.assertEqual(res.data["total"], 39000.0)
        self.assertIn("Thank you", res.data["message"])

        # Team notification + customer confirmation.
        self.assertEqual(len(mail.outbox), 2)

    def test_order_number_shape_and_uniqueness(self):
        first = self.client.post(URL, self.payload(), format="json")
        cache.clear()
        second = self.client.post(URL, self.payload(), format="json")

        numbers = [first.data["orderNumber"], second.data["orderNumber"]]
        self.assertNotEqual(numbers[0], numbers[1])
        for number in numbers:
            self.assertRegex(number, r"^MS-\d{4}-\d{4,}$")

    def test_resolves_slugs_across_all_catalogues(self):
        items = [
            {"name": "x", "slug": self.panel.slug, "price": 18500, "quantity": 1, "lineTotal": 18500},
            {"name": "y", "slug": self.inverter.slug, "price": 185000, "quantity": 1, "lineTotal": 185000},
            {"name": "z", "slug": self.battery.slug, "price": 500000, "quantity": 1, "lineTotal": 500000},
        ]
        res = self.client.post(URL, self.payload(items=items), format="json")

        self.assertEqual(res.status_code, 201)
        sources = set(OrderItem.objects.values_list("source", flat=True))
        self.assertEqual(sources, {"solar_panels", "inverters", "batteries"})

    def test_records_ip_and_user_agent(self):
        self.client.post(
            URL,
            self.payload(),
            format="json",
            HTTP_X_FORWARDED_FOR="203.0.113.9, 10.0.0.1",
            HTTP_USER_AGENT="pytest-agent",
        )

        order = Order.objects.get()
        self.assertEqual(order.ip_address, "203.0.113.9")
        self.assertEqual(order.user_agent, "pytest-agent")

    # --- price verification -------------------------------------------------

    def test_uses_server_price_not_client_price(self):
        # Browser claims the panel is Rs. 1 - the catalogue says 18500, and
        # the submitted total is recomputed against the catalogue.
        items = [
            {"name": "cheap", "slug": self.panel.slug, "price": 1, "quantity": 1, "lineTotal": 1}
        ]
        data = self.payload(items=items)
        # Send the honest total so only the per-line price is tampered with.
        data["subtotal"] = 18500
        data["total"] = 18500 + SHIPPING

        res = self.client.post(URL, data, format="json")

        self.assertEqual(res.status_code, 201)
        line = OrderItem.objects.get()
        self.assertEqual(line.price, Decimal("18500.00"))
        self.assertEqual(line.line_total, Decimal("18500.00"))

    def test_rejects_tampered_total(self):
        items = [
            {"name": "x", "slug": self.panel.slug, "price": 1, "quantity": 1, "lineTotal": 1}
        ]
        res = self.client.post(URL, self.payload(items=items), format="json")

        self.assertEqual(res.status_code, 400)
        self.assertIn("non_field_errors", res.data)
        self.assertIn("Prices have changed", str(res.data["non_field_errors"][0]))
        self.assertEqual(Order.objects.count(), 0)

    def test_rejects_unknown_slug(self):
        items = [
            {"name": "gone", "slug": "deleted-product", "price": 100, "quantity": 1, "lineTotal": 100}
        ]
        res = self.client.post(URL, self.payload(items=items), format="json")

        self.assertEqual(res.status_code, 400)
        self.assertIn("items", res.data)
        self.assertIn("deleted-product", str(res.data["items"][0]))
        self.assertEqual(Order.objects.count(), 0)

    def test_stores_client_totals_for_audit(self):
        self.client.post(URL, self.payload(), format="json")

        order = Order.objects.get()
        self.assertEqual(order.client_subtotal, Decimal("37000.00"))
        self.assertEqual(order.client_shipping, Decimal("2000.00"))
        self.assertEqual(order.client_total, Decimal("39000.00"))

    # --- field validation ---------------------------------------------------

    def test_rejects_empty_basket(self):
        res = self.client.post(URL, self.payload(items=[]), format="json")

        self.assertEqual(res.status_code, 400)
        self.assertIn("items", res.data)
        self.assertEqual(Order.objects.count(), 0)

    def test_rejects_unaccepted_terms(self):
        res = self.client.post(URL, self.payload(agreedToTerms=False), format="json")

        self.assertEqual(res.status_code, 400)
        self.assertIn("agreedToTerms", res.data)
        self.assertEqual(Order.objects.count(), 0)

    def test_rejects_invalid_state(self):
        res = self.client.post(URL, self.payload(state="Rajasthan"), format="json")

        self.assertEqual(res.status_code, 400)
        self.assertIn("state", res.data)

    def test_rejects_missing_email(self):
        data = self.payload()
        del data["email"]
        res = self.client.post(URL, data, format="json")

        self.assertEqual(res.status_code, 400)
        self.assertIn("email", res.data)

    def test_short_fields_report_per_field_errors(self):
        res = self.client.post(
            URL,
            self.payload(firstName="A", address="x", city="L", phone="123"),
            format="json",
        )

        self.assertEqual(res.status_code, 400)
        for field in ("firstName", "address", "city", "phone"):
            self.assertIn(field, res.data)

    def test_optional_fields_may_be_omitted(self):
        data = self.payload()
        for field in ("apartment", "state", "businessName", "orderNotes"):
            del data[field]

        res = self.client.post(URL, data, format="json")

        self.assertEqual(res.status_code, 201)
        order = Order.objects.get()
        self.assertEqual(order.apartment, "")
        self.assertEqual(order.state, "")

    def test_postcode_keeps_leading_zero(self):
        self.client.post(URL, self.payload(postCode="00123"), format="json")

        self.assertEqual(Order.objects.get().post_code, "00123")

    # --- throttling / settings ----------------------------------------------

    def test_throttled_after_five_orders(self):
        for _ in range(5):
            res = self.client.post(URL, self.payload(), format="json")
            self.assertEqual(res.status_code, 201)

        res = self.client.post(URL, self.payload(), format="json")
        self.assertEqual(res.status_code, 429)

    def test_settings_endpoint(self):
        res = self.client.get(SETTINGS_URL)

        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data, {"flatShipping": 2000.0, "currency": "PKR"})
