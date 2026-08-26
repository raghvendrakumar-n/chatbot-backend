"""Serializers that turn tenant design records into the frontend theme payload."""
from __future__ import annotations

from rest_framework import serializers

from .models import ChatbotDesign, MenuOption, Tenant, WelcomeMessage


class TenantSerializer(serializers.ModelSerializer):
    has_design = serializers.SerializerMethodField()

    class Meta:
        model = Tenant
        fields = ("name", "slug", "is_active", "has_design", "created_at")

    def get_has_design(self, obj: Tenant) -> bool:
        return hasattr(obj, "design")


class WelcomeMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = WelcomeMessage
        fields = ("message", "show_bot_icon", "order")


class MenuOptionSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(source="option_id")
    value = serializers.CharField(source="label")

    class Meta:
        model = MenuOption
        fields = (
            "id",
            "value",
            "order",
            "flow_key",
            "category",
            "description",
            "submit_url",
            "steps",
            "step_config",
            "is_active",
        )


class ChatbotDesignSerializer(serializers.ModelSerializer):
    logo = serializers.SerializerMethodField()
    bot_avatar = serializers.SerializerMethodField()
    launcher_icon = serializers.SerializerMethodField()
    welcome_messages = WelcomeMessageSerializer(many=True, read_only=True)
    menu_options = serializers.SerializerMethodField()
    tenant_slug = serializers.CharField(source="tenant.slug", read_only=True)
    tenant_name = serializers.CharField(source="tenant.name", read_only=True)

    class Meta:
        model = ChatbotDesign
        fields = (
            "tenant_slug",
            "tenant_name",
            "brand_name",
            "bot_name",
            "logo",
            "bot_avatar",
            "launcher_icon",
            "primary_color",
            "secondary_color",
            "header_bg_color",
            "header_text_color",
            "background_color",
            "user_bubble_color",
            "user_text_color",
            "bot_bubble_color",
            "bot_text_color",
            "font_family",
            "launcher_position",
            "header_title",
            "header_subtitle",
            "input_placeholder",
            "privacy_policy_url",
            "website_url",
            "contact_phone",
            "contact_email",
            "contact_whatsapp",
            "ai_enabled",
            "voice_enabled",
            "tts_enabled",
            "ai_system_prompt",
            "welcome_messages",
            "menu_options",
            "updated_at",
        )

    def _abs_url(self, file_field) -> str | None:
        if not file_field:
            return None
        url = file_field.url
        request = self.context.get("request")
        if request is not None:
            return request.build_absolute_uri(url)
        return url

    def get_logo(self, obj: ChatbotDesign):
        return self._abs_url(obj.logo)

    def get_bot_avatar(self, obj: ChatbotDesign):
        return self._abs_url(obj.bot_avatar)

    def get_launcher_icon(self, obj: ChatbotDesign):
        return self._abs_url(obj.launcher_icon)

    def get_menu_options(self, obj: ChatbotDesign):
        """All tenant flows (admin edits inactive items; widget filters client-side)."""
        return MenuOptionSerializer(obj.menu_options.all(), many=True).data
