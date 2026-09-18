"""Email backends that do not need outbound SMTP.

Railway's hobby plan blocks outbound SMTP ports, so the stock SMTP backend
just times out in production. Resend accepts mail over ordinary HTTPS, which
Railway does allow, so ResendEmailBackend posts each message to Resend's REST
API instead.

This is a drop-in replacement for the SMTP backend: every call site keeps
using EmailMultiAlternatives / send_mail exactly as before, only the MAILERS
setting changes. Delivery goes over urllib from the standard library so the
project gains no new dependency.
"""

import base64
import json
import logging
import urllib.error
import urllib.request
from email.message import Message

from django.core.mail.backends.base import BaseEmailBackend
from django.core.mail.message import EmailAttachment

logger = logging.getLogger(__name__)

RESEND_ENDPOINT = "https://api.resend.com/emails"

# Resend sits behind Cloudflare, which blocks urllib's default
# "Python-urllib/x.y" User-Agent outright: the request never reaches Resend and
# comes back as a plain-text "error code: 1010" with HTTP 403. Any ordinary
# User-Agent gets through, so send one identifying this app.
USER_AGENT = "madni-solar-backend/1.0"

# Headers Resend derives from the payload itself. Passing them through as
# custom headers as well would duplicate them in the delivered message.
_RESERVED_HEADERS = {"from", "to", "cc", "bcc", "reply-to", "subject"}


class ResendEmailBackend(BaseEmailBackend):
    """Send mail through the Resend HTTP API."""

    def __init__(self, api_key=None, endpoint=RESEND_ENDPOINT, timeout=10, **kwargs):
        super().__init__(**kwargs)
        self.api_key = api_key
        self.endpoint = endpoint
        self.timeout = timeout

    def send_messages(self, email_messages):
        """Send each message and return how many Resend accepted.

        One HTTP request per message: Resend has a batch endpoint, but it
        rejects attachments, and the volume here (a handful of notification
        mails per order) does not justify two code paths.
        """
        if not email_messages:
            return 0
        if not self.api_key:
            raise ValueError("RESEND_API_KEY is not set, so mail cannot be sent.")

        sent = 0
        for message in email_messages:
            if self._send(message):
                sent += 1
        return sent

    def _send(self, message):
        recipients = message.recipients()
        if not recipients:
            return False

        payload = self._payload(message)
        request = urllib.request.Request(
            self.endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "User-Agent": USER_AGENT,
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                response.read()
        except urllib.error.HTTPError as exc:
            # Resend explains rejections (unverified sender, bad address) in
            # the response body, so log it - the status code alone is useless.
            body = exc.read().decode("utf-8", "replace")
            logger.error("Resend rejected the message (HTTP %s): %s", exc.code, body)
            raise
        return True

    def _payload(self, message):
        """Translate a Django EmailMessage into Resend's JSON body."""
        payload = {
            "from": message.extra_headers.get("From", message.from_email),
            "to": list(message.to),
            "subject": str(message.subject),
        }

        # Django's plain body is text unless content_subtype says otherwise;
        # an HTML part arrives as an alternative on EmailMultiAlternatives.
        if message.content_subtype == "html":
            payload["html"] = message.body
        else:
            payload["text"] = message.body

        for alternative in getattr(message, "alternatives", []):
            if alternative.mimetype == "text/html":
                payload["html"] = alternative.content

        if message.cc:
            payload["cc"] = list(message.cc)
        if message.bcc:
            payload["bcc"] = list(message.bcc)
        if message.reply_to:
            payload["reply_to"] = list(message.reply_to)

        headers = {
            name: str(value)
            for name, value in message.extra_headers.items()
            if name.lower() not in _RESERVED_HEADERS
        }
        if headers:
            payload["headers"] = headers

        attachments = [
            attachment
            for attachment in (
                self._attachment(item) for item in message.attachments
            )
            if attachment is not None
        ]
        if attachments:
            payload["attachments"] = attachments

        return payload

    def _attachment(self, attachment):
        """Convert one Django attachment into Resend's base64 form."""
        if isinstance(attachment, EmailAttachment):
            filename, content = attachment.filename, attachment.content
        elif isinstance(attachment, Message):
            filename = attachment.get_filename()
            content = attachment.get_payload(decode=True)
        else:
            logger.warning("Skipping unsupported attachment type %r", type(attachment))
            return None

        if isinstance(content, str):
            content = content.encode("utf-8")
        return {
            "filename": filename or "attachment",
            "content": base64.b64encode(content).decode("ascii"),
        }
