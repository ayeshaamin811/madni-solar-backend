from django.urls import path

from .views import QuoteRequestCreateView

urlpatterns = [
    path("quotes/", QuoteRequestCreateView.as_view(), name="quote-create"),
]
