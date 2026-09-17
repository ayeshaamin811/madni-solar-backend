"""
URL configuration for backend project.

All API routes live under `/api/`:
    POST /api/contact/                       -> contact form
    POST /api/calculator/                    -> solar calculator form
    GET  /api/solar-panels/brands/           -> solar panel brands
    GET  /api/solar-panels/products/         -> solar panel products
    GET  /api/solar-panels/products/<slug>/  -> single product
    GET  /api/inverters/categories/           -> inverter category/brand tree
    GET  /api/inverters/products/             -> inverter products
    GET  /api/inverters/products/<slug>/      -> single product
    GET  /api/batteries/brands/               -> battery brand tree
    GET  /api/batteries/products/             -> battery products
    GET  /api/batteries/products/<slug>/      -> single product
    GET  /api/products/categories/            -> accessories category/item tree
    GET  /api/products/products/              -> accessories products
    GET  /api/products/products/<slug>/       -> single product
    POST /api/quotes/                        -> request a quote form
    POST /api/orders/                        -> checkout / place order form
    GET  /api/orders/settings/               -> flat shipping + currency
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
    path('api/', include('inverters.urls')),
    path('api/', include('batteries.urls')),
    path('api/', include('products.urls')),
    path('api/', include('quotes.urls')),
    path('api/', include('orders.urls')),
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
