import logging
import threading

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string

logger = logging.getLogger(__name__)


def notify_team(quote):
    """Email the team when a new quote request arrives.

    Same reasoning as contact/calculator's notify_team - branded HTML with a
    plain-text fallback, EmailMultiAlternatives so non-HTML clients still get
    a readable message, and a failure here must never fail the request since
    the quote is already saved in the database.

    Returns True if the message was handed to the mail backend, else False.
    """
    if not settings.QUOTE_NOTIFY_EMAILS:
        return False

    context = {"quote": quote}
    text_body = render_to_string("quotes/emails/team_notification.txt", context)
    html_body = render_to_string("quotes/emails/team_notification.html", context)

    email = EmailMultiAlternatives(
        subject=f"[Quote] New request from {quote.first_name} {quote.last_name}",
        body=text_body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=settings.QUOTE_NOTIFY_EMAILS,
        reply_to=[quote.email] if quote.email else None,
    )
    email.attach_alternative(html_body, "text/html")

    try:
        email.send()
        return True
    except Exception:
        # An SMTP outage is not the customer's problem: log it and move on.
        logger.exception("Quote notification email failed for quote id=%s", quote.id)
        return False


def send_customer_confirmation(quote):
    """Auto-reply sent to the customer, only if they gave an email address.

    Same failure handling as notify_team: an SMTP outage here must not fail
    the request, since the quote itself is already saved.

    Returns True if the confirmation was handed to the mail backend, else
    False (including when there's no customer email to send it to).
    """
    if not quote.email:
        return False

    context = {"quote": quote}
    text_body = render_to_string("quotes/emails/customer_confirmation.txt", context)
    html_body = render_to_string("quotes/emails/customer_confirmation.html", context)

    email = EmailMultiAlternatives(
        subject="We received your quote request - Madni Solar",
        body=text_body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[quote.email],
    )
    email.attach_alternative(html_body, "text/html")

    try:
        email.send()
        return True
    except Exception:
        logger.exception("Quote customer confirmation failed for quote id=%s", quote.id)
        return False


def send_quote_emails(quote):
    """Send the team notification and customer confirmation for a quote.

    Same reasoning as contact/calculator's send_*_emails - each send opens
    its own SMTP connection, so running both in a background thread keeps the
    HTTP response from waiting on SMTP round trips it never needed to see. In
    tests it runs synchronously so `mail.outbox` assertions stay deterministic.
    """

    def _send():
        notify_team(quote)
        send_customer_confirmation(quote)

    if settings.TESTING:
        _send()
    else:
        threading.Thread(target=_send, daemon=True).start()
