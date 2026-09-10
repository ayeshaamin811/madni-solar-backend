from rest_framework import status
from rest_framework.generics import CreateAPIView
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle

from .emails import send_contact_emails
from .models import ContactMessage
from .serializers import ContactMessageSerializer


class ContactRateThrottle(AnonRateThrottle):
    scope = "contact"


class ContactMessageCreateView(CreateAPIView):
    """POST /api/contact/ - public endpoint, no authentication."""

    queryset = ContactMessage.objects.all()
    serializer_class = ContactMessageSerializer
    throttle_classes = [ContactRateThrottle]

    # Both lines matter. With SessionAuthentication enabled, a browser that is
    # logged into the Django admin would make React's POST fail with
    # "403 CSRF Failed". This endpoint needs no authentication at all.
    permission_classes = []
    authentication_classes = []

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        instance = serializer.save(
            ip_address=self.get_client_ip(request),
            user_agent=request.META.get("HTTP_USER_AGENT", "")[:300],
        )
        send_contact_emails(instance)

        return Response(
            {
                "id": instance.id,
                "message": (
                    "Thank you! Your message has been received. "
                    "We will contact you soon."
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
