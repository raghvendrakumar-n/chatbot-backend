"""Seed a default tenant (NU Hospitals) with a full chatbot design.

Usage:
    python manage.py seed_tenant
"""
from __future__ import annotations

from django.core.management.base import BaseCommand

from api.ai import HOSPITAL_SYSTEM_PROMPT
from api.flows import seed_default_flows
from api.management.commands.seed_flow_templates import Command as SeedFlowTemplatesCommand
from api.models import ChatbotDesign, FlowTemplate, Tenant, WelcomeMessage

WELCOME_MESSAGES = [
    ("Welcome to NU Hospitals.", True),
    ("I am Eos, a virtual agent.", False),
    ("How can I assist you? Choose an option, type, or tap the mic to speak.", False),
]


class Command(BaseCommand):
    help = "Create/refresh the default NU Hospitals tenant and chatbot design."

    def handle(self, *args, **options):
        SeedFlowTemplatesCommand().handle()
        tenant, created = Tenant.objects.get_or_create(
            slug="nu-hospitals",
            defaults={"name": "NU Hospitals", "is_active": True},
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"Tenant {'created' if created else 'exists'}: {tenant.slug}"
            )
        )

        design, _ = ChatbotDesign.objects.update_or_create(
            tenant=tenant,
            defaults={
                "brand_name": "NU Hospitals",
                "bot_name": "Eos",
                "primary_color": "#00a19a",
                "secondary_color": "#6c757d",
                "header_bg_color": "#00a19a",
                "header_text_color": "#ffffff",
                "background_color": "#ffffff",
                "user_bubble_color": "#00a19a",
                "user_text_color": "#ffffff",
                "bot_bubble_color": "#f1f3f5",
                "bot_text_color": "#212529",
                "font_family": "'Segoe UI', Roboto, Arial, sans-serif",
                "launcher_position": ChatbotDesign.LauncherPosition.BOTTOM_RIGHT,
                "header_title": "NU Hospitals",
                "header_subtitle": "Eos · Virtual Assistant",
                "input_placeholder": "Type your message...",
                "privacy_policy_url": "https://www.nuhospitals.com/privacy-policy",
                "website_url": "https://www.nuhospitals.com",
                "contact_phone": "+91-8042489999",
                "contact_email": "care@nuhospitals.com",
                "contact_whatsapp": "+91-8951889724",
                "ai_enabled": True,
                "voice_enabled": True,
                "tts_enabled": True,
                "ai_system_prompt": HOSPITAL_SYSTEM_PROMPT,
            },
        )

        design.welcome_messages.all().delete()
        WelcomeMessage.objects.bulk_create(
            [
                WelcomeMessage(
                    design=design, order=i, message=msg, show_bot_icon=icon
                )
                for i, (msg, icon) in enumerate(WELCOME_MESSAGES)
            ]
        )

        seed_default_flows(design)

        self.stdout.write(
            self.style.SUCCESS(
                "Seeded design, "
                f"{len(WELCOME_MESSAGES)} welcome messages, "
                f"{FlowTemplate.objects.filter(is_active=True).count()} flows."
            )
        )
