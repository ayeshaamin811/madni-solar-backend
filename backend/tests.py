"""Tests for the Resend HTTP email backend.

No network here: urlopen is patched so the tests assert on the JSON payload
the backend builds, which is the part that has to match Resend's API.
"""

import base64
import json
import urllib.error
from unittest import mock

from django.core.mail import EmailMultiAlternatives
from django.test import SimpleTestCase

from .email_backends import ResendEmailBackend


class FakeResponse:
    def read(self):
        return b'{"id": "fake-id"}'

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False


def send_through_resend(message, backend=None):
    """Send a message through the backend and return the captured request."""
    captured = {}
    backend = backend or ResendEmailBackend(api_key="re_test", alias="default")

    def fake_urlopen(request, timeout=None):
        captured["url"] = request.full_url
        captured["headers"] = dict(request.header_items())
        captured["payload"] = json.loads(request.data.decode())
        captured["timeout"] = timeout
        return FakeResponse()

    with mock.patch("urllib.request.urlopen", fake_urlopen):
        captured["sent"] = backend.send_messages([message])
    return captured


class ResendEmailBackendTests(SimpleTestCase):
    def message(self, **overrides):
        options = {
            "subject": "Order 123 received",
            "body": "plain text body",
            "from_email": "Madni Solar <noreply@example.com>",
            "to": ["customer@example.com"],
        }
        options.update(overrides)
        return EmailMultiAlternatives(**options)

    def test_posts_to_resend_with_the_api_key(self):
        result = send_through_resend(self.message())

        self.assertEqual(result["sent"], 1)
        self.assertEqual(result["url"], "https://api.resend.com/emails")
        self.assertEqual(result["headers"]["Authorization"], "Bearer re_test")

    def test_sends_a_custom_user_agent(self):
        """Cloudflare fronts Resend and rejects urllib's default User-Agent."""
        result = send_through_resend(self.message())

        user_agent = result["headers"]["User-agent"]
        self.assertNotIn("Python-urllib", user_agent)
        self.assertEqual(user_agent, "madni-solar-backend/1.0")

    def test_payload_carries_both_bodies(self):
        message = self.message()
        message.attach_alternative("<p>html body</p>", "text/html")

        payload = send_through_resend(message)["payload"]

        self.assertEqual(payload["subject"], "Order 123 received")
        self.assertEqual(payload["from"], "Madni Solar <noreply@example.com>")
        self.assertEqual(payload["to"], ["customer@example.com"])
        self.assertEqual(payload["text"], "plain text body")
        self.assertEqual(payload["html"], "<p>html body</p>")

    def test_payload_carries_cc_bcc_and_reply_to(self):
        message = self.message(
            cc=["cc@example.com"],
            bcc=["bcc@example.com"],
            reply_to=["team@example.com"],
        )

        payload = send_through_resend(message)["payload"]

        self.assertEqual(payload["cc"], ["cc@example.com"])
        self.assertEqual(payload["bcc"], ["bcc@example.com"])
        self.assertEqual(payload["reply_to"], ["team@example.com"])

    def test_optional_fields_are_left_out_when_unused(self):
        payload = send_through_resend(self.message())["payload"]

        for field in ("cc", "bcc", "reply_to", "attachments", "headers"):
            self.assertNotIn(field, payload)

    def test_attachments_are_base64_encoded(self):
        message = self.message()
        message.attach("invoice.txt", "hello file", "text/plain")

        payload = send_through_resend(message)["payload"]

        self.assertEqual(len(payload["attachments"]), 1)
        attachment = payload["attachments"][0]
        self.assertEqual(attachment["filename"], "invoice.txt")
        self.assertEqual(base64.b64decode(attachment["content"]), b"hello file")

    def test_message_with_no_recipients_is_not_sent(self):
        result = send_through_resend(self.message(to=[]))

        self.assertEqual(result["sent"], 0)
        self.assertNotIn("payload", result)

    def test_missing_api_key_raises(self):
        backend = ResendEmailBackend(api_key="", alias="default")

        with self.assertRaises(ValueError):
            backend.send_messages([self.message()])

    def test_rejection_by_resend_propagates(self):
        """Callers already wrap send() in try/except, so failures must raise."""
        backend = ResendEmailBackend(api_key="re_test", alias="default")

        def fake_urlopen(request, timeout=None):
            raise urllib.error.HTTPError(
                request.full_url, 422, "Unprocessable", {}, None
            )

        with mock.patch("urllib.request.urlopen", fake_urlopen):
            with self.assertRaises(urllib.error.HTTPError):
                backend.send_messages([self.message()])
