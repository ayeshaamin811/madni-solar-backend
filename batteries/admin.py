from django.contrib import admin

from .models import Brand, Product


class SubVariantInline(admin.TabularInline):
    """Children nested under their parent brand (e.g. Huawei -> HV)."""

    model = Brand
    fk_name = "parent"
    extra = 1
    fields = ("name", "slug", "order", "description", "image")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Brand)
class BrandAdmin(admin.ModelAdmin):
    # No list_filter on `parent` - it's self-referential and Django admin's
    # related filter recurses into __str__ for every ancestor, which blows
    # the stack for this model (bit us for real on the inverters app).
    list_display = ("name", "slug", "parent", "order")
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}
    autocomplete_fields = ["parent"]
    inlines = [SubVariantInline]


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    # No prepopulated_fields on slug - it's deliberately left for the admin
    # to leave blank so Product.save() can add the "battery-" prefix (see
    # models.py); auto-filling it client-side from `name` would skip that.
    list_display = ("name", "brand", "slug", "price", "created_at")
    search_fields = ("name", "slug", "short_description")
    autocomplete_fields = ["brand"]
