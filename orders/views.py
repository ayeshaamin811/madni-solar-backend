from django.conf import settings
from rest_framework import status
from rest_framework.generics import CreateAPIView
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView

from .emails import send_order_emails
from .models import Order
from .serializers import OrderSerializer


class OrderRateThrottle(AnonRateThrottle):
    scope = "order"


class OrderCreateView(CreateAPIView):
    """POST /api/orders/ - public endpoint, no authentication.

    An order is a request to buy, not a payment: nothing is charged here, the
    sales team confirms by phone. Same shape as /api/quotes/.
    """

    queryset = Order.objects.all()
    serializer_class = OrderSerializer
    throttle_classes = [OrderRateThrottle]

    # Same reasoning as QuoteRequestCreateView: no auth at all, otherwise a
    # browser logged into the Django admin gets a CSRF failure on this
    # public form.
    permission_classes = []
    authentication_classes = []

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        order = serializer.save(
            ip_address=self.get_client_ip(request),
            user_agent=request.META.get("HTTP_USER_AGENT", "")[:300],
        )
        send_order_emails(order)

        return Response(
            {
                "id": order.id,
                "orderNumber": order.order_number,
                "total": float(order.total),
                "message": (
                    "Thank you! Your order has been received. "
                    "Our team will contact you shortly to confirm."
                ),
            },
            status=status.HTTP_201_CREATED,
        )

    @staticmethod
    def get_client_ip(request):
        forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.META.get("REMOTE_ADDR")


class OrderSettingsView(APIView):
    """GET /api/orders/settings/ - the checkout constants, so the flat
    shipping rate lives in one place instead of being hardcoded in both the
    UI and the backend.

    Read-only and cheap, so it carries the project's default anon throttle
    rather than the 5/hour form throttle - the checkout page fetches this on
    load, and 5/hour would break the page for anyone browsing normally.
    """

    permission_classes = []
    authentication_classes = []

    def get(self, request):
        return Response(
            {
                "flatShipping": float(settings.ORDER_FLAT_SHIPPING),
                "currency": settings.ORDER_CURRENCY,
            }
        )
