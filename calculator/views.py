from rest_framework import status
from rest_framework.generics import CreateAPIView
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle

from .emails import send_calculator_emails
from .models import CalculatorSubmission
from .serializers import CalculatorSubmissionSerializer


class CalculatorRateThrottle(AnonRateThrottle):
    scope = "calculator"


class CalculatorSubmissionCreateView(CreateAPIView):
    """POST /api/calculator/ - public endpoint, no authentication."""

    queryset = CalculatorSubmission.objects.all()
    serializer_class = CalculatorSubmissionSerializer
    parser_classes = [MultiPartParser, FormParser]
    throttle_classes = [CalculatorRateThrottle]

    # Same reasoning as ContactMessageCreateView: no auth at all, otherwise a
    # browser logged into the Django admin gets a CSRF failure on this
    # public form.
    permission_classes = []
    authentication_classes = []

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        instance = serializer.save(
            ip_address=self.get_client_ip(request),
            user_agent=request.META.get("HTTP_USER_AGENT", "")[:300],
        )
        send_calculator_emails(instance)

        return Response(
            {
                "id": instance.id,
                "message": (
                    "Thank you! Your solar calculation request has been "
                    "received. We will contact you soon."
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
