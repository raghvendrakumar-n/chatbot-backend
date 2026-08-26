"""Django admin so tenants + their chatbot design can be managed from the DB.

Logos and avatars are uploaded here; every colour/text setting is editable.
"""
from __future__ import annotations

from django.contrib import admin
from django.utils.html import format_html

from .models import (
    ChatbotDesign,
    FlowTemplate,
    MenuOption,
    Tenant,
    WelcomeMessage,
    TenantOwner,
    HimsApiToken,
    HimsBackendConfig,
)


class WelcomeMessageInline(admin.TabularInline):
    model = WelcomeMessage
    extra = 1


class MenuOptionInline(admin.TabularInline):
    model = MenuOption
    extra = 1


@admin.register(ChatbotDesign)
class ChatbotDesignAdmin(admin.ModelAdmin):
    list_display = ("tenant", "brand_name", "bot_name", "logo_preview", "updated_at")
    search_fields = ("tenant__name", "tenant__slug", "brand_name", "bot_name")
    autocomplete_fields = ("tenant",)
    inlines = [WelcomeMessageInline, MenuOptionInline]
    readonly_fields = ("logo_preview", "updated_at")
    fieldsets = (
        ("Tenant", {"fields": ("tenant",)}),
        (
            "Branding",
            {
                "fields": (
                    "brand_name",
                    "bot_name",
                    "logo",
                    "logo_preview",
                    "bot_avatar",
                    "launcher_icon",
                )
            },
        ),
        (
            "Colors",
            {
                "fields": (
                    "primary_color",
                    "secondary_color",
                    "header_bg_color",
                    "header_text_color",
                    "background_color",
                    "user_bubble_color",
                    "user_text_color",
                    "bot_bubble_color",
                    "bot_text_color",
                )
            },
        ),
        (
            "Typography & Layout",
            {
                "fields": (
                    "font_family",
                    "launcher_position",
                    "header_title",
                    "header_subtitle",
                    "input_placeholder",
                )
            },
        ),
        ("Links", {"fields": ("privacy_policy_url", "website_url")}),
        (
            "Contact",
            {"fields": ("contact_phone", "contact_email", "contact_whatsapp")},
        ),
        (
            "AI & Features",
            {"fields": ("ai_enabled", "voice_enabled", "tts_enabled", "ai_system_prompt")},
        ),
        ("Meta", {"fields": ("updated_at",)}),
    )

    @admin.display(description="Logo")
    def logo_preview(self, obj: ChatbotDesign):
        if obj.logo:
            return format_html(
                '<img src="{}" style="max-height:48px;border-radius:6px;" />',
                obj.logo.url,
            )
        return "—"


@admin.register(Tenant)
class TenantAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "is_active", "created_at")
    list_filter = ("is_active",)
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}


admin.site.register(WelcomeMessage)
admin.site.register(TenantOwner)
admin.site.register(MenuOption)


@admin.register(HimsBackendConfig)
class HimsBackendConfigAdmin(admin.ModelAdmin):
    list_display = ("tenant", "base_url", "organization_id", "username", "updated_at")
    search_fields = ("tenant__slug", "tenant__name", "username", "base_url")
    autocomplete_fields = ("tenant",)
    readonly_fields = ("updated_at",)


@admin.register(HimsApiToken)
class HimsApiTokenAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "tenant",
        "token_prefix",
        "expires_at",
        "revoked_at",
        "created_at",
        "last_used_at",
    )
    list_filter = ("tenant",)
    search_fields = ("name", "token_prefix", "tenant__slug")
    readonly_fields = ("token_prefix", "token_suffix", "created_at", "last_used_at")
    autocomplete_fields = ("tenant", "created_by")


@admin.register(FlowTemplate)
class FlowTemplateAdmin(admin.ModelAdmin):
    list_display = (
        "label",
        "key",
        "default_option_id",
        "category",
        "is_active",
        "sort_order",
        "updated_at",
    )
    list_filter = ("category", "is_active")
    search_fields = ("label", "key", "description")
    prepopulated_fields = {"key": ("label",)}
    ordering = ("sort_order", "id")


admin.site.site_header = "Eos Chatbot Admin"
admin.site.site_title = "Eos Chatbot Admin"
admin.site.index_title = "Chatbot tenants & design"
