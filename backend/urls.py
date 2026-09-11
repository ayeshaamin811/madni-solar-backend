"""
URL configuration for backend project.

All API routes live under `/api/`:
    POST /api/contact/                       -> contact form
    POST /api/calculator/                    -> solar calculator form
    GET  /api/solar-panels/brands/           -> solar panel brands
    GET  /api/solar-panels/products/         -> solar panel products
    GET  /api/solar-panels/products/<slug>/  -> single product
    POST /api/quotes/                        -> request a quote form
"""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('contact.urls')),
    path('api/', include('calculator.urls')),
    path('api/', include('solar_panels.urls')),
    path('api/', include('quotes.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
