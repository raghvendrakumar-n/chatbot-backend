"""Default welcome messages and flows for a newly registered tenant."""
from __future__ import annotations

from .ai import HOSPITAL_SYSTEM_PROMPT
from .flows import seed_default_flows
from .models import ChatbotDesign, WelcomeMessage

DEFAULT_WELCOME = [
    ("Welcome! How can we help you today?", True),
    ("I am your virtual assistant.", False),
    ("Choose an option below, type, or tap the mic to speak.", False),
]


def seed_default_design(design: ChatbotDesign, org_name: str, contact_email: str = "") -> None:
    """Apply starter branding, welcome messages, and flows to a new tenant design."""
    design.brand_name = org_name
    design.bot_name = "Assistant"
    design.header_title = org_name
    design.header_subtitle = "Virtual Assistant"
    design.primary_color = "#00a19a"
    design.header_bg_color = "#00a19a"
    design.user_bubble_color = "#00a19a"
    design.contact_email = contact_email
    design.ai_system_prompt = HOSPITAL_SYSTEM_PROMPT
    design.save()

    WelcomeMessage.objects.bulk_create(
        [
            WelcomeMessage(
                design=design, order=i, message=msg, show_bot_icon=icon
            )
            for i, (msg, icon) in enumerate(DEFAULT_WELCOME)
        ]
    )
    seed_default_flows(design)
