from django.urls import path

from .views import CalculatorSubmissionCreateView

urlpatterns = [
    path("calculator/", CalculatorSubmissionCreateView.as_view(), name="calculator-create"),
]
