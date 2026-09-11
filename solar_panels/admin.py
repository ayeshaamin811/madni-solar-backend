from django.contrib import admin

from .models import Brand, Product


@admin.register(Brand)
class BrandAdmin(admin.ModelAdmin):
    list_display = ("name", "slug")
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("name", "brand", "slug", "price", "created_at")
    list_filter = ("brand",)
    search_fields = ("name", "slug", "short_description")
    prepopulated_fields = {"slug": ("name",)}
    autocomplete_fields = ["brand"]
