from django.contrib import admin

from .models import Brand, Category, CategoryBrand, Product


class CategoryBrandInline(admin.TabularInline):
    model = CategoryBrand
    extra = 1
    autocomplete_fields = ["brand"]


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "order")
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}
    inlines = [CategoryBrandInline]


class SubVariantInline(admin.TabularInline):
    """Sub-variants (e.g. Inverex -> Single Phase) nested under their parent brand."""

    model = Brand
    fk_name = "parent"
    extra = 1
    fields = ("name", "slug", "order", "description", "image")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Brand)
class BrandAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "parent", "order")
    list_filter = ("parent",)
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}
    autocomplete_fields = ["parent"]
    inlines = [SubVariantInline]


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("name", "brand", "slug", "price", "created_at")
    search_fields = ("name", "slug", "short_description")
    prepopulated_fields = {"slug": ("name",)}
    autocomplete_fields = ["brand"]
