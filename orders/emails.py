import logging
import threading

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string

logger = logging.getLogger(__name__)


def notify_team(order):
    """Email the team when a new order arrives.

    Same reasoning as quotes/contact's notify_team - branded HTML with a
    plain-text fallback, EmailMultiAlternatives so non-HTML clients still get
    a readable message, and a failure here must never fail the request since
    the order is already saved in the database.

    Returns True if the message was handed to the mail backend, else False.
    """
    if not settings.ORDER_NOTIFY_EMAILS:
        return False

    context = {"order": order, "items": order.items.all()}
    text_body = render_to_string("orders/emails/team_notification.txt", context)
    html_body = render_to_string("orders/emails/team_notification.html", context)

    email = EmailMultiAlternatives(
        subject=f"[Order] {order.order_number} from {order.customer_name}",
        body=text_body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=settings.ORDER_NOTIFY_EMAILS,
        reply_to=[order.email] if order.email else None,
    )
    email.attach_alternative(html_body, "text/html")

    try:
        email.send()
        return True
    except Exception:
        # An SMTP outage is not the customer's problem: log it and move on.
        logger.exception("Order notification email failed for order id=%s", order.id)
        return False


def send_customer_confirmation(order):
    """Order-received confirmation sent to the customer.

    Unlike quotes, `email` is required at checkout, so this always has
    somewhere to go. Same failure handling as notify_team: an SMTP outage
    must not fail the request, since the order itself is already saved.

    Returns True if the confirmation was handed to the mail backend, else False.
    """
    if not order.email:
        return False

    context = {"order": order, "items": order.items.all()}
    text_body = render_to_string("orders/emails/customer_confirmation.txt", context)
    html_body = render_to_string("orders/emails/customer_confirmation.html", context)

    email = EmailMultiAlternatives(
        subject=f"Order {order.order_number} received - Madni Solar",
        body=text_body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[order.email],
    )
    email.attach_alternative(html_body, "text/html")

    try:
        email.send()
        return True
    except Exception:
        logger.exception("Order customer confirmation failed for order id=%s", order.id)
        return False


def send_order_emails(order):
    """Send the team notification and customer confirmation for an order.

    Same reasoning as quotes/contact's send_*_emails - each send opens its own
    SMTP connection, so running both in a background thread keeps the HTTP
    response from waiting on SMTP round trips it never needed to see. In tests
    it runs synchronously so `mail.outbox` assertions stay deterministic.
    """

    def _send():
        notify_team(order)
        send_customer_confirmation(order)

    if settings.TESTING:
        _send()
    else:
        threading.Thread(target=_send, daemon=True).start()
