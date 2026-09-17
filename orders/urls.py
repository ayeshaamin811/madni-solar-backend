from django.urls import path

from .views import OrderCreateView, OrderSettingsView

urlpatterns = [
    path("orders/", OrderCreateView.as_view(), name="order-create"),
    path("orders/settings/", OrderSettingsView.as_view(), name="order-settings"),
]
