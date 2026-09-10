import logging
import threading

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string

logger = logging.getLogger(__name__)


def notify_team(msg):
    """Email the team when a new contact message arrives.

    Sent as a branded HTML email with a plain-text fallback (templates in
    contact/templates/contact/emails/), using EmailMultiAlternatives so
    clients that cannot render HTML still get a readable message.

    A failure here must never fail the request: the customer's message is
    already saved in the database, which is the part that actually matters.
    Django 6.1 deprecates `fail_silently` (it is removed in 7.0), so the
    exception is caught explicitly instead.

    `reply_to` is set to the customer's address so the team can reply directly.

    Returns True if the message was handed to the mail backend, else False.
    """
    if not settings.CONTACT_NOTIFY_EMAILS:
        return False

    context = {"contact": msg}
    text_body = render_to_string("contact/emails/team_notification.txt", context)
    html_body = render_to_string("contact/emails/team_notification.html", context)

    email = EmailMultiAlternatives(
        subject=f"[Contact] {msg.subject}",
        body=text_body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=settings.CONTACT_NOTIFY_EMAILS,
        reply_to=[msg.email],
    )
    email.attach_alternative(html_body, "text/html")

    try:
        email.send()
        return True
    except Exception:
        # An SMTP outage is not the customer's problem: log it and move on.
        logger.exception("Contact notification email failed for message id=%s", msg.id)
        return False


def send_customer_confirmation(msg):
    """Auto-reply sent to the customer right after they submit the form.

    Same failure handling as notify_team: an SMTP outage here must not fail
    the request, since the message itself is already saved.

    Returns True if the confirmation was handed to the mail backend, else False.
    """
    context = {"contact": msg}
    text_body = render_to_string("contact/emails/customer_confirmation.txt", context)
    html_body = render_to_string("contact/emails/customer_confirmation.html", context)

    email = EmailMultiAlternatives(
        subject="We received your message - Madni Solar",
        body=text_body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[msg.email],
    )
    email.attach_alternative(html_body, "text/html")

    try:
        email.send()
        return True
    except Exception:
        logger.exception("Customer confirmation email failed for message id=%s", msg.id)
        return False


def send_contact_emails(msg):
    """Send the team notification and customer confirmation for a contact message.

    Each `email.send()` opens its own SMTP connection and does the full
    handshake before returning, so the two sequential sends were adding
    several seconds to every submission - the customer's "Thank you!" was
    waiting on SMTP round trips it never needed to see.

    In production this runs in a background thread so the HTTP response
    returns as soon as the message is saved to the database (the part that
    actually matters); the emails go out a moment later. In tests it runs
    synchronously so `mail.outbox` assertions right after the request stay
    deterministic.
    """

    def _send():
        notify_team(msg)
        send_customer_confirmation(msg)

    if settings.TESTING:
        _send()
    else:
        threading.Thread(target=_send, daemon=True).start()
