"""Client for hims-micro chatbot APIs (http://127.0.0.1:8004/api/v1/chatbot/).

chatbotb proxies catalog + booking calls through this module so the Angular
frontend keeps its existing envelope shape while live data comes from HIMS.

Auth + connection settings all come from the database:
``HimsBackendConfig`` (URL / org / credentials) and ``HimsApiToken`` (JWTs).
"""
from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

DEFAULT_PAGE_SIZE = 100

# In-process JWT cache (from the active DB token).
_cached_jwt: str | None = None


def enabled() -> bool:
    from . import hims_settings

    cfg = hims_settings.get_active_connection()
    return bool(cfg and (cfg.base_url or "").strip())


def organization_id() -> int | None:
    from . import hims_settings

    cfg = hims_settings.get_active_connection()
    raw = cfg.organization_id if cfg else None
    if raw in (None, ""):
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def _base_url() -> str:
    from . import hims_settings

    cfg = hims_settings.get_active_connection()
    return ((cfg.base_url if cfg else "") or "").rstrip("/")


def _normalize_bearer(token: str) -> str:
    token = (token or "").strip()
    if not token:
        return ""
    if token.lower().startswith("bearer "):
        return token
    if token.lower().startswith("token "):
        # Legacy mistaken prefix — strip and treat value as JWT.
        token = token[6:].strip()
    return f"Bearer {token}"


def login_for_jwt(*, tenant=None, password: str = "") -> str | None:
    """Obtain a fresh access JWT using DB username + password (decrypted)."""
    from . import hims_settings

    cfg = (
        hims_settings.get_or_create_config(tenant)
        if tenant is not None
        else hims_settings.get_active_connection()
    )
    if cfg is None:
        return None
    username = (cfg.username or "").strip()
    password = (password or "").strip() or cfg.get_password()
    base = (cfg.base_url or "").rstrip("/")
    if not username or not password or not base:
        return None

    url = f"{base}/api/v1/accounts/admin-login-token/"
    try:
        with httpx.Client(timeout=30.0) as client:
            resp = client.post(
                url,
                json={"username": username, "password": password},
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
            )
            resp.raise_for_status()
            data = resp.json()
        token = (data or {}).get("jwt") if isinstance(data, dict) else None
        if not token:
            logger.error("HIMS login succeeded but no jwt in response")
            return None
        return str(token)
    except httpx.HTTPError:
        logger.exception("HIMS admin-login-token failed")
        return None


def _auth_token(*, force_refresh: bool = False) -> str:
    """Return a raw JWT from DB, auto-minting when password is available."""
    global _cached_jwt

    if force_refresh:
        _cached_jwt = None

    if _cached_jwt and not force_refresh:
        return _cached_jwt

    try:
        from . import hims_settings

        db_token = hims_settings.ensure_hims_jwt(force=force_refresh)
        if db_token:
            _cached_jwt = db_token
            return _cached_jwt
    except Exception:
        logger.exception("Failed to load/refresh HIMS token from database")

    logger.warning(
        "No usable HimsApiToken in the database. "
        "Create one under Admin → HIMS Backend (password is stored encrypted)."
    )
    return ""


def _headers(*, force_refresh: bool = False) -> dict[str, str]:
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    token = _auth_token(force_refresh=force_refresh)
    bearer = _normalize_bearer(token)
    if bearer:
        headers["Authorization"] = bearer
    return headers


def _post(
    path: str,
    body: dict[str, Any],
    *,
    page_size: int | None = DEFAULT_PAGE_SIZE,
    auth: bool = False,
) -> Any:
    url = f"{_base_url()}/api/v1/chatbot/{path.lstrip('/')}"
    params = {"page_size": page_size} if page_size else None
    with httpx.Client(timeout=30.0) as client:
        headers = (
            _headers()
            if auth
            else {
                "Content-Type": "application/json",
                "Accept": "application/json",
            }
        )
        if auth and "Authorization" not in headers:
            raise httpx.HTTPStatusError(
                "No usable HIMS API token. Create one under Admin → HIMS Backend.",
                request=httpx.Request("POST", url),
                response=httpx.Response(401, request=httpx.Request("POST", url)),
            )
        resp = client.post(url, json=body, headers=headers, params=params)
        if auth and resp.status_code in (401, 403):
            # Current JWT rejected — try the next usable DB token once.
            from . import hims_settings

            used = (_cached_jwt or "").strip()
            if used:
                hims_settings.mark_jwt_rejected(used)
            headers = _headers(force_refresh=True)
            if "Authorization" not in headers:
                raise httpx.HTTPStatusError(
                    "HIMS auth failed. Create a new API token under Admin → HIMS Backend.",
                    request=resp.request,
                    response=resp,
                )
            resp = client.post(url, json=body, headers=headers, params=params)
        resp.raise_for_status()
        return resp.json()


def _results(payload: Any) -> list[dict]:
    if isinstance(payload, list):
        return payload
    if not isinstance(payload, dict):
        return []
    for key in ("results", "data", "response"):
        value = payload.get(key)
        if isinstance(value, list):
            return value
    return []


def get_branches(organization: int | None = None) -> tuple[int, str, list[dict] | str]:
    org = organization if organization is not None else organization_id()
    if org is None:
        return 400, "HIMS_ORGANIZATION_ID is required", []
    try:
        payload = _post("get-branch-list/", {"organization": org})
        branches = [
            {"id": b["id"], "branch_name": (b.get("branch_name") or "").strip()}
            for b in _results(payload)
            if b.get("id") is not None
        ]
        return 200, "Branch list", branches
    except httpx.HTTPStatusError as exc:
        logger.exception("HIMS get-branch-list failed")
        return exc.response.status_code, "HIMS branch list error", str(exc)
    except httpx.HTTPError as exc:
        logger.exception("HIMS get-branch-list unreachable")
        return 502, "Unable to reach HIMS", str(exc)


def get_departments(
    branch_id: int, organization: int | None = None
) -> tuple[int, str, list[dict] | str]:
    org = organization if organization is not None else organization_id()
    if org is None:
        return 400, "HIMS_ORGANIZATION_ID is required", []
    try:
        payload = _post(
            "get-department-list/",
            {"organization": org, "branch": int(branch_id)},
        )
        departments = [
            {
                "id": d["id"],
                # Frontend expects `department`; HIMS returns `department_title`.
                "department": d.get("department_title") or d.get("department") or "",
                "department_title": d.get("department_title") or "",
            }
            for d in _results(payload)
            if d.get("id") is not None
        ]
        return 200, "Department list", departments
    except httpx.HTTPStatusError as exc:
        logger.exception("HIMS get-department-list failed")
        return exc.response.status_code, "HIMS department list error", str(exc)
    except httpx.HTTPError as exc:
        logger.exception("HIMS get-department-list unreachable")
        return 502, "Unable to reach HIMS", str(exc)


def get_doctors(
    *,
    branch_id: int,
    department_id: int,
    organization: int | None = None,
    query: str = "",
) -> tuple[int, str, list[dict] | str]:
    org = organization if organization is not None else organization_id()
    if org is None:
        return 400, "HIMS_ORGANIZATION_ID is required", []
    body: dict[str, Any] = {
        "organization": org,
        "branch": int(branch_id),
        "department": int(department_id),
    }
    params_path = "get-doctor-list-inside-department/"
    try:
        url = f"{_base_url()}/api/v1/chatbot/{params_path}"
        req_params = {"q": query} if query else None
        with httpx.Client(timeout=30.0) as client:
            resp = client.post(
                url,
                json=body,
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
                params=req_params,
            )
            resp.raise_for_status()
            payload = resp.json()
        doctors = []
        for d in _results(payload):
            doctor_id = d.get("id")
            if doctor_id is None:
                continue
            name = d.get("doctor_name") or ""
            doctors.append(
                {
                    "id": doctor_id,
                    "doctor_name": name,
                    "qualification": d.get("qualification") or "",
                    "experience": d.get("experience") or "",
                    "profile_photo": d.get("profile_photo")
                    or "assets/userIcons/doctor-dummy.svg",
                    "profile_url": d.get("profile_url") or "",
                    "department_details": {
                        "id": int(department_id),
                        "department": d.get("department") or "",
                    },
                }
            )
        return 200, "Doctor list", doctors
    except httpx.HTTPStatusError as exc:
        logger.exception("HIMS get-doctor-list failed")
        return exc.response.status_code, "HIMS doctor list error", str(exc)
    except httpx.HTTPError as exc:
        logger.exception("HIMS get-doctor-list unreachable")
        return 502, "Unable to reach HIMS", str(exc)


def get_time_slots(
    *,
    doctor_id: int,
    department_id: int,
    branch_id: int,
    date: str,
    organization: int | None = None,
) -> tuple[int, str, list[dict] | str]:
    org = organization if organization is not None else organization_id()
    if org is None:
        return 400, "HIMS_ORGANIZATION_ID is required", []
    if not date:
        return 400, "date is required", []
    try:
        url = f"{_base_url()}/api/v1/chatbot/get-doctor-time-slot-list/"
        body = {
            "organization": org,
            "branch": int(branch_id),
            "department": int(department_id),
            "doctor": int(doctor_id),
            "date": date,
        }
        with httpx.Client(timeout=30.0) as client:
            resp = client.post(
                url,
                json=body,
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
            )
            resp.raise_for_status()
            payload = resp.json()
        slots = []
        for s in _results(payload):
            slot_id = s.get("id")
            if slot_id is None:
                continue
            slots.append(
                {
                    "id": slot_id,
                    "from_time": str(s.get("from_time") or ""),
                    "to_time": str(s.get("to_time") or ""),
                    "date_slot_id": s.get("date_slot_id"),
                    "from_datetime": s.get("date_slot__from_datetime"),
                    "to_datetime": s.get("date_slot__to_datetime"),
                }
            )
        # Extra safety: drop past slots for today (Asia/Kolkata).
        slots = _filter_future_slots(slots, date)
        if not slots:
            return 404, "No slots", "No future slots available for the selected date."
        return 200, "Available slots", slots
    except httpx.HTTPStatusError as exc:
        logger.exception("HIMS get-doctor-time-slot-list failed")
        return exc.response.status_code, "HIMS time slot error", str(exc)
    except httpx.HTTPError as exc:
        logger.exception("HIMS get-doctor-time-slot-list unreachable")
        return 502, "Unable to reach HIMS", str(exc)


def _filter_future_slots(slots: list[dict], date_str: str) -> list[dict]:
    """Keep only slots whose from_time is still in the future for today."""
    from datetime import datetime
    from zoneinfo import ZoneInfo

    try:
        selected = datetime.strptime(str(date_str).strip()[:10], "%Y-%m-%d").date()
    except ValueError:
        return slots

    try:
        now = datetime.now(ZoneInfo("Asia/Kolkata"))
    except Exception:
        now = datetime.now()

    if selected < now.date():
        return []
    if selected > now.date():
        return slots

    current = now.time().replace(microsecond=0)
    future = []
    for slot in slots:
        raw = str(slot.get("from_time") or "").strip().split(".")[0]
        if not raw:
            continue
        slot_time = None
        for candidate, fmt in ((raw[:8], "%H:%M:%S"), (raw[:5], "%H:%M")):
            try:
                slot_time = datetime.strptime(candidate, fmt).time()
                break
            except ValueError:
                continue
        if slot_time and slot_time > current:
            future.append(slot)
    return future



def create_appointment(payload: dict[str, Any]) -> tuple[int, str, Any]:
    """POST appointment-from-chatbot (requires JWT via username/password or token)."""
    org = payload.get("organization") or payload.get("tenant") or organization_id()
    if org is None:
        return 400, "HIMS_ORGANIZATION_ID is required", None

    body = {
        "tenant": org,
        "organization": org,
        "branch": payload.get("branch") or payload.get("branch_id"),
        "department": payload.get("department") or payload.get("department_id"),
        "patient_id": payload.get("patient") or payload.get("patient_id"),
        "doctor": payload.get("doctor") or payload.get("doctor_id"),
        "date_slot": payload.get("date_slot") or payload.get("date_slot_id"),
        "time_slot": payload.get("time_slot")
        or payload.get("slot_id")
        or payload.get("time_slot_id"),
        "first_name": payload.get("first_name") or "",
        "last_name": payload.get("last_name") or "",
        "mobile": payload.get("mobile") or payload.get("phone") or "",
        "email": payload.get("email") or "",
        "gender": payload.get("gender") or "",
        "age": payload.get("age") or payload.get("patient_age") or "",
        "country": payload.get("country") or payload.get("country_id") or 1,
    }

    # Split full patient_name if first/last not provided.
    full_name = (payload.get("patient_name") or "").strip()
    if full_name and not body["first_name"]:
        parts = full_name.split(None, 1)
        body["first_name"] = parts[0]
        if len(parts) > 1:
            body["last_name"] = parts[1]

    try:
        data = _post("appointment-from-chatbot/", body, page_size=None, auth=True)
        status_code = data.get("status") if isinstance(data, dict) else 200
        message = (
            data.get("message")
            if isinstance(data, dict)
            else "Appointment created successfully."
        )
        if status_code and int(status_code) >= 400:
            return int(status_code), str(message), data
        # Treat 201 as success for the chatbot envelope.
        if status_code and int(status_code) == 201:
            return 200, str(message), data
        return 200, str(message or "Your request has been submitted successfully."), data
    except httpx.HTTPStatusError as exc:
        logger.exception("HIMS appointment-from-chatbot failed")
        detail: Any
        try:
            detail = exc.response.json()
        except Exception:
            detail = exc.response.text
        if exc.response.status_code in (401, 403):
            return (
                401,
                "HIMS auth failed. Create a new API token under Admin → HIMS Backend "
                "(the stored JWT is expired or invalid).",
                detail,
            )
        return exc.response.status_code, "HIMS appointment create error", detail
    except httpx.HTTPError as exc:
        logger.exception("HIMS appointment-from-chatbot unreachable")
        return 502, "Unable to reach HIMS", str(exc)


# Backwards-compatible alias used by views.submit_appointment
create_lead = create_appointment

def patients_by_phone(phone: str) -> tuple[int, str, Any]:
    """POST patients-by-phone/ — list patients for a mobile."""
    org = organization_id()
    body: dict[str, Any] = {"phone": phone, "mobile": phone}
    if org is not None:
        body["organization"] = org
        body["tenant"] = org
    try:
        data = _post("patients-by-phone/", body, page_size=None, auth=False)
        results = _results(data) if isinstance(data, dict) else []
        status_code = int((data or {}).get("status") or 200) if isinstance(data, dict) else 200
        message = (
            (data or {}).get("message")
            if isinstance(data, dict)
            else "Patients found"
        )
        if not results or status_code == 404:
            return (
                404,
                "No patients found",
                message
                or "No patients found for this mobile number.",
            )
        return 200, str(message or "Appointments found"), results
    except httpx.HTTPStatusError as exc:
        logger.exception("HIMS patients-by-phone failed")
        try:
            detail = exc.response.json()
        except Exception:
            detail = exc.response.text
        return exc.response.status_code, "HIMS patients lookup error", detail
    except httpx.HTTPError as exc:
        logger.exception("HIMS patients-by-phone unreachable")
        return 502, "Unable to reach HIMS", str(exc)

def appointments_by_phone(phone: str) -> tuple[int, str, Any]:
    """POST appointments-by-phone/ — list upcoming appointments for a mobile."""
    org = organization_id()
    body: dict[str, Any] = {"phone": phone, "mobile": phone}
    if org is not None:
        body["organization"] = org
        body["tenant"] = org
    try:
        data = _post("appointments-by-phone/", body, page_size=None, auth=False)
        results = _results(data) if isinstance(data, dict) else []
        status_code = int((data or {}).get("status") or 200) if isinstance(data, dict) else 200
        message = (
            (data or {}).get("message")
            if isinstance(data, dict)
            else "Appointments found"
        )
        if not results or status_code == 404:
            return (
                404,
                "No appointments found",
                message
                or "No upcoming appointments found for this mobile number.",
            )
        return 200, str(message or "Appointments found"), results
    except httpx.HTTPStatusError as exc:
        logger.exception("HIMS appointments-by-phone failed")
        try:
            detail = exc.response.json()
        except Exception:
            detail = exc.response.text
        return exc.response.status_code, "HIMS appointments lookup error", detail
    except httpx.HTTPError as exc:
        logger.exception("HIMS appointments-by-phone unreachable")
        return 502, "Unable to reach HIMS", str(exc)


def cancel_appointment(appointment_id: int | str) -> tuple[int, str, Any]:
    """POST cancel-appointment-from-chatbot/."""
    body = {
        "appointmentId": appointment_id,
        "appointment_id": appointment_id,
    }
    try:
        data = _post(
            "cancel-appointment-from-chatbot/", body, page_size=None, auth=True
        )
        status_code = int((data or {}).get("status") or 200) if isinstance(data, dict) else 200
        message = (
            (data or {}).get("message")
            if isinstance(data, dict)
            else "Appointment cancelled successfully."
        )
        payload = (data or {}).get("data") if isinstance(data, dict) else data
        if status_code >= 400:
            return status_code, str(message), payload
        return 200, str(message), payload
    except httpx.HTTPStatusError as exc:
        logger.exception("HIMS cancel-appointment failed")
        try:
            detail = exc.response.json()
        except Exception:
            detail = exc.response.text
        return exc.response.status_code, "HIMS cancel error", detail
    except httpx.HTTPError as exc:
        logger.exception("HIMS cancel-appointment unreachable")
        return 502, "Unable to reach HIMS", str(exc)


def reschedule_appointment(payload: dict[str, Any]) -> tuple[int, str, Any]:
    """POST reschedule-appointment-from-chatbot/."""
    body = {
        "appointmentId": payload.get("appointmentId") or payload.get("appointment_id"),
        "date": payload.get("date") or payload.get("appointment_date"),
        "time_slot": payload.get("time_slot")
        or payload.get("slot_id")
        or payload.get("time_slot_id"),
        "slot_id": payload.get("slot_id") or payload.get("time_slot"),
        "date_slot": payload.get("date_slot") or payload.get("date_slot_id"),
        "from_time": payload.get("from_time"),
        "to_time": payload.get("to_time"),
    }
    try:
        data = _post(
            "reschedule-appointment-from-chatbot/", body, page_size=None, auth=True
        )
        status_code = int((data or {}).get("status") or 200) if isinstance(data, dict) else 200
        message = (
            (data or {}).get("message")
            if isinstance(data, dict)
            else "Appointment rescheduled successfully."
        )
        result = (data or {}).get("data") if isinstance(data, dict) else data
        if status_code >= 400:
            return status_code, str(message), result
        return 200, str(message), result
    except httpx.HTTPStatusError as exc:
        logger.exception("HIMS reschedule-appointment failed")
        try:
            detail = exc.response.json()
        except Exception:
            detail = exc.response.text
        return exc.response.status_code, "HIMS reschedule error", detail
    except httpx.HTTPError as exc:
        logger.exception("HIMS reschedule-appointment unreachable")
        return 502, "Unable to reach HIMS", str(exc)


def list_appointments(filters: dict[str, Any] | None = None) -> tuple[int, str, Any]:
    """POST appointments-list/ — all appointments for the configured org."""
    org = organization_id()
    if org is None:
        return 400, "HIMS organization id is required", []
    body: dict[str, Any] = {"organization": org, "tenant": org, "limit": 100}
    if isinstance(filters, dict):
        body.update({k: v for k, v in filters.items() if v not in (None, "")})
    try:
        data = _post("appointments-list/", body, page_size=None, auth=True)
        status_code = int((data or {}).get("status") or 200) if isinstance(data, dict) else 200
        message = (
            (data or {}).get("message")
            if isinstance(data, dict)
            else "Appointment list"
        )
        results = _results(data) if isinstance(data, dict) else []
        if status_code >= 400:
            return status_code, str(message), results
        return 200, str(message or "Appointment list"), results
    except httpx.HTTPStatusError as exc:
        logger.exception("HIMS appointments-list failed")
        try:
            detail = exc.response.json()
        except Exception:
            detail = exc.response.text
        return exc.response.status_code, "HIMS appointments list error", detail
    except httpx.HTTPError as exc:
        logger.exception("HIMS appointments-list unreachable")
        return 502, "Unable to reach HIMS", str(exc)


def dashboard_stats() -> tuple[int, str, Any]:
    """POST dashboard-stats/ — aggregate appointment metrics for admin."""
    org = organization_id()
    if org is None:
        return 400, "HIMS organization id is required", None
    body = {"organization": org, "tenant": org, "chatbot_only": True}
    try:
        data = _post("dashboard-stats/", body, page_size=None, auth=True)
        status_code = int((data or {}).get("status") or 200) if isinstance(data, dict) else 200
        message = (
            (data or {}).get("message")
            if isinstance(data, dict)
            else "Dashboard stats"
        )
        payload = (data or {}).get("data") if isinstance(data, dict) else data
        if status_code >= 400:
            return status_code, str(message), payload
        return 200, str(message or "Dashboard stats"), payload
    except httpx.HTTPStatusError as exc:
        logger.exception("HIMS dashboard-stats failed")
        try:
            detail = exc.response.json()
        except Exception:
            detail = exc.response.text
        return exc.response.status_code, "HIMS dashboard error", detail
    except httpx.HTTPError as exc:
        logger.exception("HIMS dashboard-stats unreachable")
        return 502, "Unable to reach HIMS", str(exc)

def list_doctors(filters: dict[str, Any] | None = None) -> tuple[int, str, Any]:
    """POST doctors-list/ - doctors for the configured org (admin)."""
    org = organization_id()
    if org is None:
        return 400, "HIMS organization id is required", []
    body: dict[str, Any] = {"organization": org, "tenant": org, "limit": 200}
    if isinstance(filters, dict):
        body.update({k: v for k, v in filters.items() if v not in (None, "")})
    try:
        data = _post("doctors-list/", body, page_size=None, auth=True)
        status_code = int((data or {}).get("status") or 200) if isinstance(data, dict) else 200
        message = (
            (data or {}).get("message")
            if isinstance(data, dict)
            else "Doctor list"
        )
        results = _results(data) if isinstance(data, dict) else []
        if status_code >= 400:
            return status_code, str(message), results
        return 200, str(message or "Doctor list"), results
    except httpx.HTTPStatusError as exc:
        logger.exception("HIMS doctors-list failed")
        try:
            detail = exc.response.json()
        except Exception:
            detail = exc.response.text
        return exc.response.status_code, "HIMS doctors list error", detail
    except httpx.HTTPError as exc:
        logger.exception("HIMS doctors-list unreachable")
        return 502, "Unable to reach HIMS", str(exc)
