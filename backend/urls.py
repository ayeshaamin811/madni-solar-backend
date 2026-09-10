"""
URL configuration for backend project.

All API routes live under `/api/`:
    POST /api/contact/      -> contact form
    POST /api/calculator/   -> solar calculator form
"""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('contact.urls')),
    path('api/', include('calculator.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
