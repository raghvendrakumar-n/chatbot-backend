"""Chatbot flow runtime — main menu catalog lives in ``FlowTemplate`` (database).

Seed or refresh templates::

    python manage.py seed_flow_templates

Edit templates in Django admin → Flow templates, or per-tenant via MenuOption.
"""
from __future__ import annotations

# ---------------------------------------------------------------------------
# Internal conversation steps (frontend state machine only)
# ---------------------------------------------------------------------------

INTERNAL_STEPS: list[dict] = [
    {"id": 8, "key": "self", "label": "Self", "description": "Booking for self"},
    {"id": 9, "key": "other", "label": "Family/Friends", "description": "Booking for someone else"},
    {"id": 10, "key": "privacy_agree", "label": "Agree", "description": "Accept privacy policy"},
    {"id": 11, "key": "privacy_decline", "label": "No", "description": "Decline privacy policy"},
    {"id": 12, "key": "gender_male", "label": "Male", "description": "Patient gender male"},
    {"id": 13, "key": "gender_female", "label": "Female", "description": "Patient gender female"},
    {"id": 14, "key": "confirm_booking_yes", "label": "Yes", "description": "Confirm appointment booking"},
    {"id": 15, "key": "book_another", "label": "Book another", "description": "Restart doctor picker"},
    {"id": 16, "key": "additional_info_prompt", "label": "Yes", "description": "Offer additional info step"},
    {"id": 17, "key": "skip_additional", "label": "No", "description": "Skip additional info"},
    {"id": 18, "key": "additional_info_yes", "label": "Yes", "description": "Enter additional info text"},
    {"id": 19, "key": "additional_info_no", "label": "No", "description": "Submit without extra info"},
    {"id": 22, "key": "cancel_confirm_yes", "label": "Yes, cancel it", "description": "Confirm cancellation"},
    {"id": 23, "key": "cancel_confirm_no", "label": "No, keep it", "description": "Keep appointment"},
    {"id": 24, "key": "reschedule_confirm_yes", "label": "Yes, reschedule", "description": "Proceed to slot picker"},
    {"id": 25, "key": "reschedule_confirm_no", "label": "No", "description": "Keep original slot"},
    {"id": 26, "key": "reschedule_confirm_slot", "label": "Confirm reschedule", "description": "Submit new slot"},
]

# ---------------------------------------------------------------------------
# Intent keywords (free-text / voice → main menu option id)
# ---------------------------------------------------------------------------

INTENTS: list[dict] = [
    {
        "id": "book_appointment",
        "option_id": 1,
        "label": "Appointment with doctor",
        "keywords": [
            "book appointment", "appointment with doctor", "see a doctor",
            "consult doctor", "doctor appointment", "book doctor",
            "schedule appointment", "fix appointment",
            "अपॉइंटमेंट", "अपॉइंटमेंट बुक", "डॉक्टर से मिलना",
            "डॉक्टर से मिलना है", "डॉक्टर बुक", "मुलाकात बुक",
            "appointment book", "doctor milna", "doctor se milna",
        ],
    },
    {
        "id": "find_doctor",
        "option_id": 2,
        "label": "Find doctor",
        "keywords": [
            "find doctor", "search doctor", "doctor list", "available doctors",
            "which doctor", "locate doctor",
            "डॉक्टर खोजो", "डॉक्टर ढूंढो", "डॉक्टर चाहिए",
            "doctor chahiye", "doctor dhundo", "doctor khojo",
        ],
    },
    {
        "id": "video_consultation",
        "option_id": 3,
        "label": "Book video consultation",
        "keywords": [
            "video consultation", "video consult", "online consultation",
            "teleconsult", "virtual consult", "online doctor",
            "वीडियो कंसल्ट", "ऑनलाइन डॉक्टर", "वीडियो अपॉइंटमेंट",
            "online consult", "video doctor",
        ],
    },
    {
        "id": "cancel_appointment",
        "option_id": 20,
        "label": "Cancel appointment",
        "keywords": [
            "cancel appointment", "cancel booking", "cancel my appointment",
            "remove appointment", "delete appointment",
            "अपॉइंटमेंट कैंसल", "कैंसल अपॉइंटमेंट", "अपॉइंटमेंट रद्द",
            "appointment cancel", "cancel karo",
        ],
    },
    {
        "id": "reschedule_appointment",
        "option_id": 21,
        "label": "Reschedule appointment",
        "keywords": [
            "reschedule", "reschedule appointment", "change appointment",
            "postpone appointment", "move appointment", "change date",
            "change slot",
            "अपॉइंटमेंट बदलो", "रिस्केड्यूल", "तारीख बदलो", "समय बदलो",
            "appointment badlo", "date badlo",
        ],
    },
    {
        "id": "surgery_enquiry",
        "option_id": 4,
        "label": "Surgery enquiry",
        "keywords": [
            "surgery", "surgery enquiry", "procedure", "operation", "surgical",
            "सर्जरी", "ऑपरेशन", "सर्जरी पूछताछ", "operation ke bare",
        ],
    },
    {
        "id": "international_patient",
        "option_id": 5,
        "label": "International patient query",
        "keywords": [
            "international patient", "international query", "overseas patient",
            "foreign patient", "medical tourism",
            "अंतरराष्ट्रीय मरीज", "विदेशी मरीज", "international patient",
        ],
    },
    {
        "id": "connect_with_us",
        "option_id": 6,
        "label": "Connect with us",
        "keywords": [
            "connect with us", "contact us", "phone number", "email",
            "whatsapp", "contact info",
            "संपर्क", "फोन नंबर", "व्हाट्सएप", "contact karo", "number chahiye",
        ],
    },
    {
        "id": "customer_care",
        "option_id": 7,
        "label": "Connect with our Customercare",
        "keywords": [
            "customer care", "customercare", "helpline", "support",
            "help desk", "call centre", "call center",
            "कस्टमर केयर", "हेल्पलाइन", "सहायता", "help chahiye",
        ],
    },
]

# ---------------------------------------------------------------------------
# Application-level flows (auth, tenant, embed)
# ---------------------------------------------------------------------------

APPLICATION_FLOWS: dict = {
    "auth": {
        "signup": {
            "path": "POST /api/auth/signup",
            "steps": [
                "User submits organization + email + password",
                "Backend creates User, Tenant, ChatbotDesign, TenantOwner, Token",
                "Default menu seeded from FlowTemplate (database)",
                "Frontend stores token → redirects to /chatbot-admin",
            ],
        },
        "login": {
            "path": "POST /api/auth/login",
            "steps": [
                "Resolve user by email or username",
                "Authenticate password",
                "Require TenantOwner link",
                "Return token + tenant",
            ],
        },
    },
    "tenant_design": {
        "load": "GET /api/tenants/{slug}/design (public)",
        "save": "PATCH /api/tenants/{slug}/design (owner token)",
        "upload": "POST /api/tenants/{slug}/design/upload (owner token)",
    },
    "embed": {
        "steps": [
            "Host page loads eos-embed.js",
            "Lightweight launcher button shown (no Angular yet)",
            "User clicks → iframe loads /widget?embed=1&tenant={slug}&autoOpen=1",
            "ChatbotComponent loads design + opens chat",
            "postMessage eos-open / eos-close resizes parent iframe",
            "On close iframe destroyed; launcher restored",
        ],
    },
    "chat": {
        "menu_click": "chooseOptions(option_id) → structured flow",
        "free_text": "detectIntent() → option_id OR POST /api/ai/chat",
        "voice": "MediaRecorder → POST /api/ai/transcribe → intent or AI",
        "catalog": "GET /api/branches, /departments, /doctors, /time-slots",
        "appointments": "GET/POST /api/appointments/*",
    },
}


def _ensure_flow_templates() -> None:
    """Auto-seed FlowTemplate rows on first use if the table is empty."""
    from .models import FlowTemplate

    if FlowTemplate.objects.filter(is_active=True).exists():
        return
    from .management.commands.seed_flow_templates import Command as SeedFlowTemplatesCommand

    SeedFlowTemplatesCommand().handle()


def _active_flow_templates():
    from .models import FlowTemplate

    _ensure_flow_templates()
    return FlowTemplate.objects.filter(is_active=True).order_by("sort_order", "id")


def _flow_option_ids() -> dict[str, int]:
    return {
        t.key: t.default_option_id
        for t in _active_flow_templates()
        if t.default_option_id is not None
    }


def default_step_config(flow_key: str) -> list[dict]:
    """Return a copy of the default step configuration for a flow key."""
    from .models import FlowTemplate

    _ensure_flow_templates()
    template = FlowTemplate.objects.filter(key=flow_key, is_active=True).first()
    if template and template.step_config:
        return [dict(step) for step in template.step_config]
    return []


def default_menu_options() -> list[tuple[int, str]]:
    """Default (option_id, label) pairs for new tenants."""
    return [
        (t.default_option_id, t.label)
        for t in _active_flow_templates()
        if t.default_option_id is not None
    ]


def seed_default_flows(design) -> None:
    """Persist full default flow definitions for a tenant design from FlowTemplate."""
    from .models import MenuOption

    templates = list(_active_flow_templates())
    design.menu_options.all().delete()
    if not templates:
        return

    MenuOption.objects.bulk_create(
        [
            MenuOption(
                design=design,
                order=i,
                option_id=t.default_option_id or (100 + i),
                flow_key=t.key,
                label=t.label,
                category=t.category,
                description=t.description,
                submit_url=t.submit_url,
                steps=t.steps or [],
                step_config=[dict(step) for step in (t.step_config or [])],
                is_active=True,
            )
            for i, t in enumerate(templates)
        ]
    )


def main_menu_flow_by_id(flow_id: int) -> dict | None:
    from .models import FlowTemplate

    _ensure_flow_templates()
    template = FlowTemplate.objects.filter(default_option_id=flow_id).first()
    if template:
        return template.to_main_menu_dict()
    return None


def flows_payload() -> dict:
    """Serializable flow catalog for GET /api/flows."""
    templates = list(_active_flow_templates())
    option_ids = _flow_option_ids()
    main_menu = [t.to_main_menu_dict() for t in templates]
    step_templates = {
        t.key: [dict(step) for step in (t.step_config or [])]
        for t in templates
        if t.step_config
    }

    return {
        "main_menu": main_menu,
        "step_templates": step_templates,
        "internal_steps": INTERNAL_STEPS,
        "intents": [
            {
                "id": intent["id"],
                "option_id": option_ids[intent["id"]],
                "label": intent["label"],
                "keywords": intent["keywords"],
            }
            for intent in INTENTS
            if intent["id"] in option_ids
        ],
        "application": APPLICATION_FLOWS,
    }


def detect_intent(text: str) -> dict | None:
    """Map free-text to a main menu option id."""
    normalized = " ".join(str(text or "").lower().split()).strip()
    if not normalized:
        return None

    option_ids = _flow_option_ids()
    best: dict | None = None
    best_score = -1

    for intent in INTENTS:
        option_id = option_ids.get(intent["id"])
        if option_id is None:
            continue
        for keyword in intent["keywords"]:
            if keyword in normalized:
                score = len(keyword) + (10 if normalized == keyword else 0)
                if best is None or score > best_score:
                    best_score = score
                    best = {
                        "id": intent["id"],
                        "optionId": option_id,
                        "label": intent["label"],
                        "confidence": min(0.99, 0.55 + len(keyword) / 40),
                    }

    return best
