"""
URL configuration for backend project.

All API routes live under `/api/`:
    POST /api/contact/   -> contact form
"""
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('contact.urls')),
]
