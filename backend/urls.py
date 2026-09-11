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
from django.contrib import admin
from django.urls import include, path, re_path
from django.views.static import serve

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('contact.urls')),
    path('api/', include('calculator.urls')),
    path('api/', include('solar_panels.urls')),
    path('api/', include('quotes.urls')),
]

# django.conf.urls.static.static() no-ops when DEBUG is False (it's meant for
# dev only), so call the view it wraps directly - this app has no other media
# host (e.g. S3), so product/brand photos and calculator bill uploads need to
# be reachable in production too.
urlpatterns += [
    re_path(
        r'^%s(?P<path>.*)$' % settings.MEDIA_URL.lstrip('/'),
        serve,
        {'document_root': settings.MEDIA_ROOT},
    ),
]
