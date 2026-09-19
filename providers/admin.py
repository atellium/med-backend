from django.contrib import admin

from providers.forms import ProviderAdminForm
from providers.models import Provider, ProviderCategory, ProviderHour


class ProviderHourInline(admin.TabularInline):
    model = ProviderHour
    extra = 1
    fields = (
        "days",
        "opens_at",
        "closes_at",
    )
    ordering = (
        "opens_at",
        "id",
    )


@admin.register(ProviderCategory)
class ProviderCategoryAdmin(admin.ModelAdmin):
    fields = (
        "name",
        "label",
        "slug",
        "aliases",
        "image",
        "sort_order",
        "is_active",
        "is_featured",
    )
    list_display = (
        "name",
        "label",
        "slug",
        "sort_order",
        "is_active",
        "is_featured",
        "updated_at",
    )
    list_display_links = ("name",)
    list_editable = ("sort_order", "is_active", "is_featured")
    list_filter = ("is_active", "is_featured")
    search_fields = ("name", "label", "slug", "aliases")
    ordering = ("sort_order", "name")
    prepopulated_fields = {"slug": ("label",)}
    readonly_fields = ("created_at", "updated_at")
    list_per_page = 50
    save_on_top = True


@admin.register(Provider)
class ProviderAdmin(admin.ModelAdmin):
    form = ProviderAdminForm
    inlines = (ProviderHourInline,)
    fieldsets = (
        (
            "General Info",
            {
                "fields": (
                    "name",
                    "slug",
                    "owner",
                    "categories",
                    "description",
                )
            },
        ),
        (
            "Media",
            {
                "fields": (
                    "cover_image",
                )
            },
        ),
        (
            "Contact",
            {
                "fields": (
                    "phone",
                    "alternate_numbers",
                    "whatsapp",
                    "email",
                    "website",
                )
            },
        ),
        (
            "Address",
            {
                "fields": (
                    "address",
                    "landmark",
                    "locality",
                    "city",
                    "pincode",
                    "latitude",
                    "longitude",
                )
            },
        ),
        (
            "Services & Facilities",
            {
                "fields": (
                    "offerings",
                    "services",
                    "facilities",
                )
            },
        ),
        (
            "SEO",
            {
                "fields": (
                    "seo_title",
                    "seo_description",
                    "seo_keywords",
                )
            },
        ),
        (
            "Status",
            {
                "fields": (
                    "is_verified",
                    "is_featured",
                    "is_medicine_enquiry",
                    "is_test_book",
                    "is_active",
                )
            },
        ),
    )
    list_display = (
        "name",
        "owner",
        "city",
        "locality",
        "phone",
        "is_verified",
        "is_featured",
        "is_medicine_enquiry",
        "is_test_book",
        "is_active",
        "updated_at",
    )
    list_display_links = ("name",)
    list_editable = (
        "is_verified",
        "is_featured",
        "is_medicine_enquiry",
        "is_test_book",
        "is_active",
    )
    list_filter = (
        "is_active",
        "is_verified",
        "is_featured",
        "is_medicine_enquiry",
        "is_test_book",
        "categories",
        "city",
        "owner",
    )
    search_fields = (
        "name",
        "slug",
        "phone",
        "alternate_numbers",
        "whatsapp",
        "email",
        "website",
        "address",
        "landmark",
        "locality",
        "pincode",
        "categories__name",
        "categories__label",
        "owner__phone",
        "owner__email",
        "owner__full_name",
    )
    autocomplete_fields = ("categories", "city", "owner")
    ordering = ("-is_featured", "name")
    readonly_fields = ("slug", "created_at", "updated_at")
    list_per_page = 50
    save_on_top = True


@admin.register(ProviderHour)
class ProviderHourAdmin(admin.ModelAdmin):
    fields = (
        "provider",
        "days",
        "opens_at",
        "closes_at",
    )
    list_display = (
        "provider",
        "day_names_display",
        "opens_at",
        "closes_at",
        "updated_at",
    )
    list_display_links = ("provider",)
    list_filter = ("opens_at",)
    search_fields = (
        "provider__name",
        "provider__slug",
        "provider__phone",
        "provider__locality",
    )
    autocomplete_fields = ("provider",)
    ordering = (
        "provider__name",
        "opens_at",
        "id",
    )
    readonly_fields = ("created_at", "updated_at")
    list_per_page = 50
    save_on_top = True

    @admin.display(description="Days")
    def day_names_display(self, obj):
        return ", ".join(obj.day_names)
