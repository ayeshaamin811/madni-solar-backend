from django.contrib import admin

from .models import Category, Item, Product


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "order")
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}


class SubItemInline(admin.TabularInline):
    """Children nested under their parent item (e.g. Cables -> Nafees Cables).

    `category` is deliberately left out of this form - a child always
    inherits its parent's category (see Item.save()), so it's never shown
    or asked for here.
    """

    model = Item
    fk_name = "parent"
    extra = 1
    fields = ("name", "slug", "order", "description", "image")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Item)
class ItemAdmin(admin.ModelAdmin):
    # No list_filter on `parent` - it's self-referential and Django admin's
    # related filter recurses into __str__ for every ancestor, which blows
    # the stack for this kind of model (bit us for real on the inverters app).
    list_display = ("name", "slug", "category", "parent", "order")
    list_filter = ("category",)
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}
    autocomplete_fields = ["category", "parent"]
    inlines = [SubItemInline]


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    # No prepopulated_fields on slug - it's deliberately left for the admin
    # to leave blank so Product.save() can add the category prefix (see
    # models.py); auto-filling it client-side from `name` would skip that.
    list_display = ("name", "item", "slug", "price", "created_at")
    search_fields = ("name", "slug", "short_description")
    autocomplete_fields = ["item"]
