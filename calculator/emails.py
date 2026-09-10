import logging
import os
import threading
from email.mime.image import MIMEImage
from email.utils import make_msgid

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string

logger = logging.getLogger(__name__)

# The compressed bill upload is always re-encoded to .jpg (see
# calculator/utils.py:compress_bill_image), but PDFs pass through untouched.
IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp")

# Display labels for the "loads" JSON keys, in the same order as the
# frontend's Load Calculator (src/pages/CalculatorPage/CalculatorPage.jsx).
LOAD_LABELS = (
    ("ledBulbs", "LED Bulbs"),
    ("tubeLights", "Tube Lights"),
    ("fans", "Fans"),
    ("refrigerators", "Refrigerators"),
    ("ac1Ton", "AC 1 Ton (Inverter)"),
    ("ac1_5Ton", "AC 1.5 Ton (Inverter)"),
    ("ac2Ton", "AC 2 Ton (Inverter)"),
    ("ups1kw", "UPS (1kW)"),
    ("motor1hp", "Motor (1HP)"),
)


def _load_lines(submission):
    """Human-readable "Label: qty" lines, skipping appliances left at 0."""
    return [
        f"{label}: {submission.loads.get(key, 0)}"
        for key, label in LOAD_LABELS
        if submission.loads.get(key, 0)
    ]


def _inline_bill_image(submission):
    """Build an inline (Content-ID) image attachment for an image bill.

    Embedding the bytes with a cid: reference means the bill shows up right
    inside the email body in any client, instead of a dead link to a path on
    the server's disk that the team can't otherwise reach. Returns
    (mime_image, cid) for an image bill, or (None, None) for a PDF, a missing
    file, or no file at all - callers fall back to the plain-text mention.
    """
    bill_file = submission.bill_file
    if not bill_file or not bill_file.name.lower().endswith(IMAGE_EXTENSIONS):
        return None, None

    try:
        with bill_file.open("rb") as f:
            data = f.read()
    except (FileNotFoundError, OSError):
        logger.warning("Bill file missing on disk for submission id=%s", submission.id)
        return None, None

    cid = make_msgid(domain="madnisolar.pk")[1:-1]  # strip the surrounding <>
    image = MIMEImage(data)
    image.add_header("Content-ID", f"<{cid}>")
    image.add_header(
        "Content-Disposition", "inline", filename=os.path.basename(bill_file.name)
    )
    return image, cid


def notify_team(submission):
    """Email the team when a new calculator submission arrives.

    Same reasoning as contact/emails.py:notify_team - branded HTML with a
    plain-text fallback, EmailMultiAlternatives so non-HTML clients still get
    a readable message, and a failure here must never fail the request since
    the submission is already saved in the database.

    Returns True if the message was handed to the mail backend, else False.
    """
    if not settings.CALCULATOR_NOTIFY_EMAILS:
        return False

    bill_image, bill_image_cid = _inline_bill_image(submission)
    context = {
        "submission": submission,
        "load_lines": _load_lines(submission),
        "bill_image_cid": bill_image_cid,
    }
    text_body = render_to_string("calculator/emails/team_notification.txt", context)
    html_body = render_to_string("calculator/emails/team_notification.html", context)

    email = EmailMultiAlternatives(
        subject=f"[Calculator] New request from {submission.full_name}",
        body=text_body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=settings.CALCULATOR_NOTIFY_EMAILS,
        reply_to=[submission.email],
    )
    email.attach_alternative(html_body, "text/html")

    if bill_image is not None:
        # Content-Disposition: inline + a matching Content-ID (set in
        # _inline_bill_image) is enough for mail clients to render this next
        # to the cid: reference in the HTML body rather than as a download.
        email.attach(bill_image)

    try:
        email.send()
        return True
    except Exception:
        # An SMTP outage is not the customer's problem: log it and move on.
        logger.exception(
            "Calculator notification email failed for submission id=%s", submission.id
        )
        return False


def send_customer_confirmation(submission):
    """Auto-reply sent to the customer right after they submit the calculator.

    Same failure handling as notify_team: an SMTP outage here must not fail
    the request, since the submission itself is already saved.

    Returns True if the confirmation was handed to the mail backend, else False.
    """
    context = {"submission": submission, "load_lines": _load_lines(submission)}
    text_body = render_to_string("calculator/emails/customer_confirmation.txt", context)
    html_body = render_to_string("calculator/emails/customer_confirmation.html", context)

    email = EmailMultiAlternatives(
        subject="We received your solar calculation request - Madni Solar",
        body=text_body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[submission.email],
    )
    email.attach_alternative(html_body, "text/html")

    try:
        email.send()
        return True
    except Exception:
        logger.exception(
            "Calculator customer confirmation failed for submission id=%s", submission.id
        )
        return False


def send_calculator_emails(submission):
    """Send the team notification and customer confirmation for a submission.

    Same reasoning as contact/emails.py:send_contact_emails - each send opens
    its own SMTP connection, so running both in a background thread keeps the
    HTTP response from waiting on SMTP round trips it never needed to see. In
    tests it runs synchronously so `mail.outbox` assertions stay deterministic.
    """

    def _send():
        notify_team(submission)
        send_customer_confirmation(submission)

    if settings.TESTING:
        _send()
    else:
        threading.Thread(target=_send, daemon=True).start()
