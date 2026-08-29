"""API views.

Every endpoint returns the ``{ code, message, response }`` envelope the Angular
frontend's ``ChatService`` expects, so the component logic needs no changes.
"""
from __future__ import annotations

import random

from django.conf import settings
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from rest_framework.decorators import api_view, parser_classes, authentication_classes, permission_classes
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import IsAuthenticated

from django.utils.text import slugify

from . import ai, data, hims, hims_settings
from .flows import flows_payload, main_menu_flow_by_id, default_step_config, seed_default_flows
from .management.commands.seed_flow_templates import Command as SeedFlowTemplatesCommand
from .intents import detect_intent
from .models import ChatbotDesign, MenuOption, Tenant, TenantOwner, WelcomeMessage
from .serializers import ChatbotDesignSerializer, TenantSerializer

# Scalar design fields that the admin panel may update.
DESIGN_SCALAR_FIELDS = [
    "brand_name",
    "bot_name",
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
]


def envelope(code: int = 200, message: str = "OK", response=None) -> Response:
    return Response({"code": code, "message": message, "response": response})


def _authenticate_user(request: Request):
    """Return user from Authorization token, or None."""
    auth = TokenAuthentication()
    result = auth.authenticate(request)
    return result[0] if result else None


def _tenant_owned_by(user, slug: str) -> bool:
    try:
        return user.tenant_owner.tenant.slug == slug
    except (TenantOwner.DoesNotExist, AttributeError):
        return False


def _require_tenant_owner(request: Request, slug: str) -> Response | None:
    """Return an error envelope if the user may not manage this tenant."""
    user = _authenticate_user(request)
    if not user:
        return envelope(401, "Authentication required", None)
    if not _tenant_owned_by(user, slug):
        return envelope(403, "You can only manage your own tenant", None)
    return None


# --- Health -----------------------------------------------------------------


@api_view(["GET"])
def root(request: Request) -> Response:
    return Response(
        {
            "name": "Eos Chatbot API (Django)",
            "docs": "/api/",
            "admin": "/admin/",
            "status": "ok",
        }
    )


@api_view(["GET"])
def health(request: Request) -> Response:
    return Response(
        {
            "status": "ok",
            "openai_configured": bool(settings.OPENAI_API_KEY),
            "groq_configured": bool(settings.GROQ_API_KEY),
            "hims_configured": hims.enabled(),
            "hims_organization_id": hims.organization_id(),
        }
    )


# --- Tenant design ----------------------------------------------------------


@api_view(["GET"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def tenants(request: Request) -> Response:
    """Return the logged-in tenant owner's organization only."""
    try:
        owner = request.user.tenant_owner
    except TenantOwner.DoesNotExist:
        return envelope(403, "No tenant linked to this account", None)
    return envelope(200, "Tenant list", [TenantSerializer(owner.tenant).data])


@csrf_exempt
@api_view(["GET", "PATCH", "PUT"])
def tenant_design(request: Request, slug: str) -> Response:
    """Read or update a tenant's full chatbot design (DB-driven)."""
    active_only = request.method == "GET"
    lookup = {"slug": slug}
    if active_only:
        lookup["is_active"] = True
    tenant = get_object_or_404(Tenant, **lookup)

    design = getattr(tenant, "design", None)
    if design is None:
        if request.method == "GET":
            return envelope(404, "Design not configured for this tenant", None)
        design = ChatbotDesign.objects.create(tenant=tenant, brand_name=tenant.name)

    if request.method != "GET":
        denied = _require_tenant_owner(request, slug)
        if denied is not None:
            return denied
        _apply_design_update(design, request.data)

    payload = ChatbotDesignSerializer(design, context={"request": request}).data
    message = "Chatbot design" if request.method == "GET" else "Design saved"
    return envelope(200, message, payload)


def _apply_design_update(design: ChatbotDesign, body: dict) -> None:
    """Update scalar fields and (optionally) replace nested lists."""
    for field in DESIGN_SCALAR_FIELDS:
        if field in body and body[field] is not None:
            setattr(design, field, body[field])
    design.save()

    welcome = body.get("welcome_messages")
    if isinstance(welcome, list):
        design.welcome_messages.all().delete()
        WelcomeMessage.objects.bulk_create(
            [
                WelcomeMessage(
                    design=design,
                    order=item.get("order", i),
                    message=(item.get("message") or "").strip(),
                    show_bot_icon=bool(item.get("show_bot_icon", False)),
                )
                for i, item in enumerate(welcome)
                if (item.get("message") or "").strip()
            ]
        )

    menu = body.get("menu_options")
    if isinstance(menu, list):
        design.menu_options.all().delete()
        rows = []
        for i, item in enumerate(menu):
            label = (item.get("value") or item.get("label") or "").strip()
            option_id = item.get("id", item.get("option_id"))
            if not label or option_id is None:
                continue
            template = main_menu_flow_by_id(int(option_id)) or {}
            flow_key = (
                item.get("flow_key")
                or template.get("key")
                or f"flow_{option_id}"
            )[:80]
            step_config = item.get("step_config")
            if not isinstance(step_config, list) or not step_config:
                step_config = default_step_config(flow_key)
            rows.append(
                MenuOption(
                    design=design,
                    order=item.get("order", i),
                    option_id=int(option_id),
                    flow_key=flow_key,
                    label=label,
                    category=item.get("category")
                    or template.get("category")
                    or MenuOption.Category.BOOKING,
                    description=item.get("description")
                    or template.get("description")
                    or "",
                    submit_url=item.get("submit_url")
                    or template.get("submit_url")
                    or "",
                    steps=item.get("steps") or template.get("steps") or [],
                    step_config=step_config,
                    is_active=bool(item.get("is_active", True)),
                )
            )
        MenuOption.objects.bulk_create(rows)


@csrf_exempt
@api_view(["POST"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser, FormParser])
def upload_design_image(request: Request, slug: str) -> Response:
    """Upload a logo / bot avatar / launcher icon for a tenant's design."""
    denied = _require_tenant_owner(request, slug)
    if denied is not None:
        return denied

    tenant = get_object_or_404(Tenant, slug=slug)
    design = getattr(tenant, "design", None)
    if design is None:
        design = ChatbotDesign.objects.create(tenant=tenant, brand_name=tenant.name)

    field = request.data.get("field", "logo")
    if field not in ("logo", "bot_avatar", "launcher_icon"):
        return envelope(400, "field must be logo, bot_avatar, or launcher_icon", None)

    upload = request.FILES.get("file")
    if upload is None:
        return envelope(400, "file is required", None)

    setattr(design, field, upload)
    design.save()
    payload = ChatbotDesignSerializer(design, context={"request": request}).data
    return envelope(200, f"{field} uploaded", payload)


# --- Catalog ----------------------------------------------------------------


@api_view(["GET"])
def countries(request: Request) -> Response:
    return envelope(200, "Country available for booking", data.get_countries())


@api_view(["GET"])
def branches(request: Request) -> Response:
    if hims.enabled():
        code, message, response = hims.get_branches()
        return envelope(code, message, response)
    return envelope(200, "Branch list", data.get_branches())


@api_view(["GET"])
def departments(request: Request) -> Response:
    branch_id = request.query_params.get("branch_id")
    if branch_id is None:
        return envelope(400, "branch_id is required", None)
    if hims.enabled():
        code, message, response = hims.get_departments(branch_id)
        return envelope(code, message, response)
    return envelope(200, "Department list", data.get_departments(branch_id))


@api_view(["GET"])
def doctors(request: Request) -> Response:
    department_id = request.query_params.get("department_id")
    if department_id is None:
        return envelope(400, "department_id is required", None)
    if hims.enabled():
        branch_id = request.query_params.get("branch_id")
        if branch_id is None:
            return envelope(400, "branch_id is required when HIMS is enabled", None)
        code, message, response = hims.get_doctors(
            branch_id=int(branch_id),
            department_id=int(department_id),
            query=request.query_params.get("q", ""),
        )
        return envelope(code, message, response)
    return envelope(200, "Doctor list", data.get_doctors(department_id))


@api_view(["GET"])
def surgeries(request: Request) -> Response:
    department_id = request.query_params.get("department_id")
    if department_id is None:
        return envelope(400, "department_id is required", None)
    return envelope(200, "Surgery list", data.get_surgeries(department_id))


@api_view(["GET"])
def time_slots(request: Request) -> Response:
    if hims.enabled():
        doctor_id = request.query_params.get("doctor_id")
        department_id = request.query_params.get("department_id")
        branch_id = request.query_params.get("branch_id")
        date = request.query_params.get("date", "")
        missing = [
            name
            for name, value in (
                ("doctor_id", doctor_id),
                ("department_id", department_id),
                ("branch_id", branch_id),
                ("date", date),
            )
            if not value
        ]
        if missing:
            return envelope(400, f"{', '.join(missing)} required", None)
        code, message, response = hims.get_time_slots(
            doctor_id=int(doctor_id),
            department_id=int(department_id),
            branch_id=int(branch_id),
            date=date,
        )
        return envelope(code, message, response)

    slots = data.get_time_slots()
    if not slots:
        return envelope(404, "No slots", "No slots available for the selected date.")
    return envelope(200, "Available slots", slots)


# --- Appointments -----------------------------------------------------------


@api_view(["POST"])
def submit_appointment(request: Request) -> Response:
    payload = request.data if isinstance(request.data, dict) else {}
    url = request.query_params.get("url", "")
    if hims.enabled():
        code, message, response = hims.create_lead(payload)
        if code == 200:
            return envelope(
                200,
                message,
                {
                    "reference_id": (
                        (
                            (response or {}).get("appointment_no")
                            or (response or {}).get("reference_id")
                        )
                        if isinstance(response, dict)
                        else None
                    )
                    or f"HIMS-{random.randint(100000, 999999)}",
                    "submitted_to": "hims-micro/appointment-from-chatbot",
                    "details": payload,
                    "hims": response,
                },
            )
        return envelope(code, message, response)

    reference_id = f"NU-{random.randint(100000, 999999)}"
    return envelope(
        200,
        "Your request has been submitted successfully.",
        {
            "reference_id": reference_id,
            "submitted_to": url,
            "details": payload,
        },
    )

@api_view(["GET"])
def patients_by_phone(request: Request) -> Response:
    phone = request.query_params.get("phone", "")
    if hims.enabled():
        code, message, response = hims.patients_by_phone(phone)
        return envelope(code, message, response)
    found = data.find_appointments_by_phone(phone)
    if not found:
        return envelope(
            404,
            "No patients found",
            "No patients found for this mobile number.",
        )
    return envelope(200, "Patients found", found)


@api_view(["GET"])
def appointments_by_phone(request: Request) -> Response:
    phone = request.query_params.get("phone", "")
    if hims.enabled():
        code, message, response = hims.appointments_by_phone(phone)
        return envelope(code, message, response)
    found = data.find_appointments_by_phone(phone)
    if not found:
        return envelope(
            404,
            "No appointments found",
            "No upcoming appointments found for this mobile number.",
        )
    return envelope(200, "Appointments found", found)


@api_view(["POST"])
def cancel_appointment(request: Request) -> Response:
    appointment_id = request.data.get("appointmentId") or request.data.get(
        "appointment_id"
    )
    if hims.enabled():
        if not appointment_id:
            return envelope(400, "appointmentId is required", None)
        code, message, response = hims.cancel_appointment(appointment_id)
        return envelope(code, message, response)

    appointment = data.find_appointment(appointment_id) if appointment_id else None
    if not appointment or appointment["status"] != "booked":
        return envelope(404, "Appointment not found", None)
    appointment["status"] = "cancelled"
    return envelope(200, "Appointment cancelled successfully.", dict(appointment))


@api_view(["POST"])
def reschedule_appointment(request: Request) -> Response:
    body = request.data if isinstance(request.data, dict) else {}
    if hims.enabled():
        code, message, response = hims.reschedule_appointment(body)
        return envelope(code, message, response)

    appointment_id = body.get("appointmentId")
    appointment = data.find_appointment(appointment_id) if appointment_id else None
    if not appointment or appointment["status"] != "booked":
        return envelope(404, "Appointment not found", None)
    appointment["appointment_date"] = body.get("date")
    appointment["slot_id"] = body.get("slot_id")
    appointment["from_time"] = body.get("from_time")
    appointment["to_time"] = body.get("to_time")
    return envelope(200, "Appointment rescheduled successfully.", dict(appointment))


@csrf_exempt
@api_view(["POST"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def reset_tenant_flows(request: Request, slug: str) -> Response:
    """Restore default flows from the system template catalog."""
    denied = _require_tenant_owner(request, slug)
    if denied is not None:
        return denied

    tenant = get_object_or_404(Tenant, slug=slug)
    design = getattr(tenant, "design", None)
    if design is None:
        design = ChatbotDesign.objects.create(tenant=tenant, brand_name=tenant.name)

    SeedFlowTemplatesCommand().handle()
    seed_default_flows(design)
    payload = ChatbotDesignSerializer(design, context={"request": request}).data
    return envelope(200, "Default flows restored", payload)


def _next_tenant_option_id(design: ChatbotDesign) -> int:
    ids = list(design.menu_options.values_list("option_id", flat=True))
    return (max(ids) + 1) if ids else 100


@csrf_exempt
@api_view(["POST"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def create_tenant_flow(request: Request, slug: str) -> Response:
    """Create a new custom flow for this tenant."""
    denied = _require_tenant_owner(request, slug)
    if denied is not None:
        return denied

    tenant = get_object_or_404(Tenant, slug=slug)
    design = getattr(tenant, "design", None)
    if design is None:
        design = ChatbotDesign.objects.create(tenant=tenant, brand_name=tenant.name)

    body = request.data if isinstance(request.data, dict) else {}
    label = (body.get("label") or body.get("value") or "New flow").strip()
    if not label:
        return envelope(400, "label is required", None)

    flow_key = (body.get("flow_key") or "").strip()
    if not flow_key:
        base = slugify(label)[:60] or "custom_flow"
        flow_key = f"{base}_{design.menu_options.count() + 1}"

    category = body.get("category") or MenuOption.Category.INFO
    if category not in dict(MenuOption.Category.choices):
        category = MenuOption.Category.INFO

    step_config = body.get("step_config")
    if not isinstance(step_config, list) or not step_config:
        step_config = default_step_config(flow_key)
    if not step_config:
        step_config = [
            {
                "key": "intro",
                "type": "message",
                "message": "How can I help you?",
                "show_bot_icon": True,
                "enabled": True,
                "order": 0,
            },
            {
                "key": "submit",
                "type": "submit",
                "message": "Thank you!",
                "show_bot_icon": True,
                "enabled": True,
                "order": 1,
            },
        ]

    option_id = body.get("id") or body.get("option_id")
    if option_id is None:
        option_id = _next_tenant_option_id(design)
    else:
        option_id = int(option_id)

    if design.menu_options.filter(option_id=option_id).exists():
        return envelope(409, f"Flow id {option_id} already exists", None)

    order = design.menu_options.count()
    MenuOption.objects.create(
        design=design,
        order=order,
        option_id=option_id,
        flow_key=flow_key[:80],
        label=label,
        category=category,
        description=(body.get("description") or "").strip(),
        submit_url=(body.get("submit_url") or "").strip(),
        steps=body.get("steps") or [],
        step_config=step_config,
        is_active=bool(body.get("is_active", True)),
    )

    payload = ChatbotDesignSerializer(design, context={"request": request}).data
    return envelope(201, "Flow created", payload)


@csrf_exempt
@api_view(["DELETE"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def delete_tenant_flow(request: Request, slug: str, option_id: int) -> Response:
    """Delete a tenant flow by menu option id."""
    denied = _require_tenant_owner(request, slug)
    if denied is not None:
        return denied

    tenant = get_object_or_404(Tenant, slug=slug)
    design = getattr(tenant, "design", None)
    if design is None:
        return envelope(404, "Design not found", None)

    deleted, _ = design.menu_options.filter(option_id=option_id).delete()
    if not deleted:
        return envelope(404, "Flow not found", None)

    for i, flow in enumerate(design.menu_options.order_by("order", "id")):
        if flow.order != i:
            flow.order = i
            flow.save(update_fields=["order"])

    payload = ChatbotDesignSerializer(design, context={"request": request}).data
    return envelope(200, "Flow deleted", payload)


# --- Flow definitions -------------------------------------------------------


@api_view(["GET"])
def flows_list(_request: Request) -> Response:
    """Return main menu flows, internal steps, intents, and app-level flow docs."""
    return envelope(200, "OK", flows_payload())


# --- AI ---------------------------------------------------------------------


@api_view(["POST"])
def detect_intent_view(request: Request) -> Response:
    text = request.data.get("text", "")
    intent = detect_intent(text)
    if intent is None:
        return envelope(404, "No intent matched", None)
    return envelope(200, "OK", intent)


@csrf_exempt
@api_view(["POST"])
def chat(request: Request) -> Response:
    message = (request.data.get("message") or "").strip()
    history = request.data.get("history") or []
    if not message:
        return envelope(400, "message is required", None)

    # Optionally use the tenant's custom system prompt.
    system_prompt = ""
    tenant_slug = request.data.get("tenant")
    if tenant_slug:
        tenant = Tenant.objects.filter(slug=tenant_slug, is_active=True).first()
        design = getattr(tenant, "design", None) if tenant else None
        if design and design.ai_system_prompt:
            system_prompt = design.ai_system_prompt

    code, message_text, response = ai.ask_hospital_assistant(
        message, history, system_prompt
    )
    return envelope(code, message_text, response)


@csrf_exempt
@api_view(["POST"])
@parser_classes([MultiPartParser, FormParser, JSONParser])
def transcribe(request: Request) -> Response:
    upload = request.FILES.get("file")
    if upload is None:
        return envelope(400, "audio file is required", "No audio file uploaded.")
    language = (request.data.get("language") or "").strip()
    context = (request.data.get("context") or "").strip()
    code, message_text, response = ai.transcribe_audio(
        upload.name,
        upload.read(),
        upload.content_type,
        language=language,
        context=context,
    )
    return envelope(code, message_text, response)


# --- HIMS backend settings (admin UI) --------------------------------------


def _require_hims_tenant(request: Request):
    """Return (tenant, error_response). Tenant comes from the logged-in owner."""
    try:
        tenant = request.user.tenant_owner.tenant
    except (TenantOwner.DoesNotExist, AttributeError):
        return None, envelope(403, "No tenant linked to this account", None)
    return tenant, None


@api_view(["GET", "PATCH"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def hims_backend_settings(request: Request) -> Response:
    """Read or update HIMS connection settings; GET also lists DB tokens."""
    tenant, err = _require_hims_tenant(request)
    if err:
        return err

    if request.method == "GET":
        return envelope(200, "HIMS settings", hims_settings.get_public_config(tenant=tenant))

    payload = request.data if isinstance(request.data, dict) else {}
    hims_settings.save_config(tenant, payload)
    return envelope(
        200,
        "HIMS settings saved",
        hims_settings.get_public_config(tenant=tenant),
    )


@api_view(["GET", "POST"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def hims_tokens(request: Request) -> Response:
    """List or create OpenAI-style HIMS API tokens (stored in DB)."""
    tenant, err = _require_hims_tenant(request)
    if err:
        return err

    if request.method == "GET":
        return envelope(
            200,
            "HIMS API tokens",
            {
                "tokens": hims_settings.list_tokens(tenant),
                "expiry_presets_days": list(hims_settings.EXPIRY_PRESETS_DAYS),
            },
        )

    payload = request.data if isinstance(request.data, dict) else {}
    code, message, config = hims_settings.create_token(
        tenant, payload, user=request.user
    )
    return envelope(code, message, config)


@api_view(["DELETE"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def hims_token_detail(request: Request, token_id: int) -> Response:
    """Revoke a stored HIMS API token."""
    tenant, err = _require_hims_tenant(request)
    if err:
        return err

    code, message, config = hims_settings.revoke_token(tenant, token_id)
    return envelope(code, message, config)


@api_view(["POST"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def hims_generate_token(request: Request) -> Response:
    """Create a DB-backed HIMS token (alias of POST /settings/hims/tokens)."""
    tenant, err = _require_hims_tenant(request)
    if err:
        return err

    payload = request.data if isinstance(request.data, dict) else {}
    code, message, config = hims_settings.create_token(
        tenant, payload, user=request.user
    )
    return envelope(code, message, config)


@api_view(["GET"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def admin_dashboard(request: Request) -> Response:
    """Dashboard analytics for the logged-in tenant (counts + chart data)."""
    tenant, err = _require_hims_tenant(request)
    if err:
        return err

    meta = {
        "tenant": {"name": tenant.name, "slug": tenant.slug},
    }

    if hims.enabled():
        code, message, stats = hims.dashboard_stats()
        if code == 200 and isinstance(stats, dict):
            return envelope(
                200,
                message or "Dashboard",
                {**meta, "appointments": stats},
            )
        return envelope(
            code,
            message or "Dashboard partial",
            {**meta, "appointments": None, "appointments_error": stats},
        )

    from . import data as demo
    from datetime import date, timedelta

    rows = list(demo.APPOINTMENTS)
    by_status: dict[str, int] = {}
    by_branch_map: dict[str, int] = {}
    by_dept_map: dict[str, int] = {}
    by_doctor_map: dict[str, int] = {}
    for row in rows:
        key = str(row.get("status") or "booked")
        by_status[key] = by_status.get(key, 0) + 1
        branch = str(row.get("branch_name") or "Unknown")
        by_branch_map[branch] = by_branch_map.get(branch, 0) + 1
        dept = str(row.get("department") or "Unknown")
        by_dept_map[dept] = by_dept_map.get(dept, 0) + 1
        doctor = str(row.get("doctor_name") or "Unknown")
        by_doctor_map[doctor] = by_doctor_map.get(doctor, 0) + 1

    total = len(rows)
    booked = by_status.get("booked", 0)
    completed = by_status.get("completed", 0)
    rescheduled = by_status.get("rescheduled", 0)
    cancelled = by_status.get("cancelled", 0)
    denom = max(total, 1)
    today = date.today()
    daily_trend = []
    for offset in range(14):
        day = today - timedelta(days=13 - offset)
        daily_trend.append({"date": day.isoformat(), "count": 0})
    if daily_trend:
        daily_trend[-1]["count"] = total

    return envelope(
        200,
        "Dashboard (demo data)",
        {
            **meta,
            "appointments": {
                "total": total,
                "today": 0,
                "booked": booked,
                "completed": completed,
                "rescheduled": rescheduled,
                "cancelled": cancelled,
                "chatbot_sourced": total,
                "last_7_days": total,
                "last_30_days": total,
                "this_month": total,
                "upcoming": booked,
                "rates": {
                    "booked_pct": round((booked / denom) * 100, 1),
                    "completed_pct": round((completed / denom) * 100, 1),
                    "rescheduled_pct": round((rescheduled / denom) * 100, 1),
                    "cancelled_pct": round((cancelled / denom) * 100, 1),
                    "completion_rate": round((completed / denom) * 100, 1),
                    "cancellation_rate": round((cancelled / denom) * 100, 1),
                },
                "by_branch": [
                    {"branch_id": None, "branch_name": name, "count": count}
                    for name, count in sorted(
                        by_branch_map.items(), key=lambda x: -x[1]
                    )
                ],
                "by_department": [
                    {"department_id": None, "department_name": name, "count": count}
                    for name, count in sorted(
                        by_dept_map.items(), key=lambda x: -x[1]
                    )
                ],
                "by_doctor": [
                    {"doctor_id": None, "doctor_name": name, "count": count}
                    for name, count in sorted(
                        by_doctor_map.items(), key=lambda x: -x[1]
                    )
                ],
                "daily_trend": daily_trend,
            },
        },
    )


@api_view(["GET"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def admin_appointments(request: Request) -> Response:
    """Appointments list for admin (defaults to chatbot-sourced only)."""
    _tenant, err = _require_hims_tenant(request)
    if err:
        return err

    raw_chatbot = request.query_params.get("chatbot_only")
    if raw_chatbot is None or str(raw_chatbot).strip() == "":
        chatbot_only = True
    else:
        chatbot_only = str(raw_chatbot).strip().lower() in ("1", "true", "yes", "on")

    filters = {
        "status": request.query_params.get("status"),
        "branch": request.query_params.get("branch")
        or request.query_params.get("branch_id"),
        "date_from": request.query_params.get("date_from"),
        "date_to": request.query_params.get("date_to"),
        "chatbot_only": chatbot_only,
        "limit": request.query_params.get("limit") or "100",
    }

    if hims.enabled():
        code, message, response = hims.list_appointments(filters)
        return envelope(code, message, response)

    from . import data as demo

    rows = list(demo.APPOINTMENTS)
    status_filter = (filters.get("status") or "").strip().lower()
    if status_filter:
        rows = [r for r in rows if str(r.get("status") or "").lower() == status_filter]
    return envelope(200, "Appointment list (demo)", rows)


@api_view(["GET"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def admin_doctors(request: Request) -> Response:
    """Doctors list for admin (optional branch / department / search filters)."""
    _tenant, err = _require_hims_tenant(request)
    if err:
        return err

    filters = {
        "branch": request.query_params.get("branch")
        or request.query_params.get("branch_id"),
        "department": request.query_params.get("department")
        or request.query_params.get("department_id"),
        "q": request.query_params.get("q"),
        "limit": request.query_params.get("limit") or "200",
    }

    if hims.enabled():
        code, message, response = hims.list_doctors(filters)
        return envelope(code, message, response)

    from . import data as demo

    rows: list[dict] = []
    for dept_id, doctors in (demo.DOCTORS_BY_DEPARTMENT or {}).items():
        for d in doctors:
            rows.append(
                {
                    **d,
                    "department": (d.get("department_details") or {}).get("department")
                    or "",
                    "branch_name": "",
                    "departments": [
                        {
                            "id": (d.get("department_details") or {}).get("id"),
                            "name": (d.get("department_details") or {}).get("department")
                            or "",
                        }
                    ],
                    "branches": [],
                    "is_available": True,
                }
            )
    q = (filters.get("q") or "").strip().lower()
    if q:
        rows = [r for r in rows if q in str(r.get("doctor_name") or "").lower()]
    return envelope(200, "Doctor list (demo)", rows)
