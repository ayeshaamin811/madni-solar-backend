import io
import json
import shutil
import tempfile

from django.conf import settings
from django.core import mail
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from PIL import Image
from rest_framework.test import APITestCase

from .models import CalculatorSubmission

URL = "/api/calculator/"


def make_test_image(name="bill.png", size=(2000, 1400), color=(200, 60, 20)):
    """A real, decodable image for upload tests - big enough that a passing
    compression test actually proves the file was downscaled, not just
    accepted as-is."""
    buffer = io.BytesIO()
    Image.new("RGB", size, color).save(buffer, format="PNG")
    return SimpleUploadedFile(name, buffer.getvalue(), content_type="image/png")

VALID_LOADS = {
    "ledBulbs": 6,
    "tubeLights": 2,
    "fans": 4,
    "refrigerators": 1,
    "ac1Ton": 1,
    "ac1_5Ton": 0,
    "ac2Ton": 0,
    "ups1kw": 1,
    "motor1hp": 0,
}

PAYLOAD = {
    "meterType": "single",
    "billAmount": "15000",
    "billUnits": "450",
    "fullName": "Ali Raza",
    "phone": "+92 300 1234567",
    "email": "ali@example.com",
    "houseArea": "5",
    "address": "House 12, Street 3, Lahore",
    "loads": json.dumps(VALID_LOADS),
    "loadCalculated": "3.5",
}


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class CalculatorAPITests(APITestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        # Uploaded test files land in the overridden MEDIA_ROOT, not the
        # real media/ directory - clean it up so tests don't leave junk on disk.
        shutil.rmtree(settings.MEDIA_ROOT, ignore_errors=True)

    def setUp(self):
        # Throttle counters live in the cache, so start each test from clean.
        cache.clear()

    def test_creates_submission(self):
        res = self.client.post(URL, PAYLOAD, format="multipart")

        self.assertEqual(res.status_code, 201)
        self.assertEqual(CalculatorSubmission.objects.count(), 1)

        submission = CalculatorSubmission.objects.get()
        self.assertEqual(submission.full_name, "Ali Raza")
        self.assertEqual(submission.meter_type, "single")
        self.assertEqual(submission.loads, VALID_LOADS)
        self.assertEqual(res.data["id"], submission.id)
        self.assertIn("Thank you", res.data["message"])

    def test_records_ip_and_user_agent(self):
        res = self.client.post(
            URL,
            PAYLOAD,
            format="multipart",
            HTTP_X_FORWARDED_FOR="203.0.113.9, 10.0.0.1",
            HTTP_USER_AGENT="Mozilla/5.0 (test)",
        )

        self.assertEqual(res.status_code, 201)
        submission = CalculatorSubmission.objects.get()
        self.assertEqual(submission.ip_address, "203.0.113.9")
        self.assertEqual(submission.user_agent, "Mozilla/5.0 (test)")

    def test_bill_file_is_optional(self):
        res = self.client.post(URL, PAYLOAD, format="multipart")

        self.assertEqual(res.status_code, 201)
        self.assertFalse(CalculatorSubmission.objects.get().bill_file)

    def test_accepts_bill_file_upload(self):
        res = self.client.post(
            URL, {**PAYLOAD, "billFile": make_test_image()}, format="multipart"
        )

        self.assertEqual(res.status_code, 201)
        self.assertTrue(CalculatorSubmission.objects.get().bill_file)

    def test_compresses_large_bill_image(self):
        original = make_test_image(name="bill.png", size=(2400, 1800))
        original_size = original.size  # captured before the upload consumes the stream
        res = self.client.post(URL, {**PAYLOAD, "billFile": original}, format="multipart")

        self.assertEqual(res.status_code, 201)
        stored = CalculatorSubmission.objects.get().bill_file

        # Re-encoded to a compact JPEG regardless of the uploaded format/name.
        self.assertTrue(stored.name.endswith(".jpg"))

        with stored.open("rb") as f:
            image = Image.open(f)
            image.load()
            self.assertLessEqual(max(image.size), 1600)

        self.assertLess(stored.size, original_size)

    def test_rejects_corrupt_image_file(self):
        bill_file = SimpleUploadedFile(
            "bill.jpg", b"not-actually-an-image", content_type="image/jpeg"
        )
        res = self.client.post(URL, {**PAYLOAD, "billFile": bill_file}, format="multipart")

        self.assertEqual(res.status_code, 400)
        self.assertIn("billFile", res.data)
        self.assertEqual(CalculatorSubmission.objects.count(), 0)

    def test_rejects_oversized_bill_file(self):
        bill_file = SimpleUploadedFile(
            "bill.jpg", b"x" * (5 * 1024 * 1024 + 1), content_type="image/jpeg"
        )
        res = self.client.post(URL, {**PAYLOAD, "billFile": bill_file}, format="multipart")

        self.assertEqual(res.status_code, 400)
        self.assertIn("billFile", res.data)
        self.assertEqual(CalculatorSubmission.objects.count(), 0)

    def test_rejects_unsupported_bill_file_type(self):
        bill_file = SimpleUploadedFile(
            "bill.exe", b"not-a-bill", content_type="application/octet-stream"
        )
        res = self.client.post(URL, {**PAYLOAD, "billFile": bill_file}, format="multipart")

        self.assertEqual(res.status_code, 400)
        self.assertIn("billFile", res.data)

    def test_rejects_invalid_meter_type(self):
        res = self.client.post(URL, {**PAYLOAD, "meterType": "quad"}, format="multipart")

        self.assertEqual(res.status_code, 400)
        self.assertIn("meterType", res.data)

    def test_rejects_zero_bill_amount(self):
        res = self.client.post(URL, {**PAYLOAD, "billAmount": "0"}, format="multipart")

        self.assertEqual(res.status_code, 400)
        self.assertIn("billAmount", res.data)

    def test_rejects_short_address(self):
        res = self.client.post(URL, {**PAYLOAD, "address": "abc"}, format="multipart")

        self.assertEqual(res.status_code, 400)
        self.assertIn("address", res.data)

    def test_rejects_missing_required_fields(self):
        res = self.client.post(URL, {"phone": "0300"}, format="multipart")

        self.assertEqual(res.status_code, 400)
        for field in (
            "meterType",
            "billAmount",
            "billUnits",
            "fullName",
            "email",
            "houseArea",
            "address",
            "loads",
            "loadCalculated",
        ):
            self.assertIn(field, res.data)

    def test_rejects_malformed_loads_json(self):
        res = self.client.post(URL, {**PAYLOAD, "loads": "{not json"}, format="multipart")

        self.assertEqual(res.status_code, 400)
        self.assertIn("loads", res.data)

    def test_rejects_unknown_load_key(self):
        loads = {**VALID_LOADS, "heater": 1}
        res = self.client.post(URL, {**PAYLOAD, "loads": json.dumps(loads)}, format="multipart")

        self.assertEqual(res.status_code, 400)
        self.assertIn("loads", res.data)

    def test_rejects_out_of_range_load_quantity(self):
        loads = {**VALID_LOADS, "fans": 11}
        res = self.client.post(URL, {**PAYLOAD, "loads": json.dumps(loads)}, format="multipart")

        self.assertEqual(res.status_code, 400)
        self.assertIn("loads", res.data)

    def test_loads_defaults_missing_keys_to_zero(self):
        res = self.client.post(URL, {**PAYLOAD, "loads": json.dumps({"fans": 2})}, format="multipart")

        self.assertEqual(res.status_code, 201)
        self.assertEqual(CalculatorSubmission.objects.get().loads["ledBulbs"], 0)

    def test_throttles_after_five_submissions(self):
        for i in range(5):
            res = self.client.post(URL, PAYLOAD, format="multipart")
            self.assertEqual(res.status_code, 201, f"request {i + 1} should pass")

        res = self.client.post(URL, PAYLOAD, format="multipart")
        self.assertEqual(res.status_code, 429)
        self.assertIn("detail", res.data)
        self.assertEqual(CalculatorSubmission.objects.count(), 5)

    def test_no_auth_required(self):
        res = self.client.post(URL, PAYLOAD, format="multipart")
        self.assertEqual(res.status_code, 201)

    def test_team_email_embeds_bill_image_inline(self):
        res = self.client.post(
            URL, {**PAYLOAD, "billFile": make_test_image()}, format="multipart"
        )
        self.assertEqual(res.status_code, 201)

        team_email = mail.outbox[0]
        image_attachments = [
            a for a in team_email.attachments if a.get_content_maintype() == "image"
        ]
        self.assertEqual(len(image_attachments), 1)
        self.assertIn("Content-ID", image_attachments[0])

        # The HTML body references the same Content-ID via cid:, not a bare
        # filesystem path.
        html_body = team_email.alternatives[0][0]
        cid = image_attachments[0]["Content-ID"].strip("<>")
        self.assertIn(f"cid:{cid}", html_body)

    def test_team_email_falls_back_to_text_mention_without_bill_file(self):
        res = self.client.post(URL, PAYLOAD, format="multipart")
        self.assertEqual(res.status_code, 201)

        team_email = mail.outbox[0]
        self.assertEqual(len(team_email.attachments), 0)
