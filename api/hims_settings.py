"""HIMS integration settings stored entirely in the database.

Connection settings live on ``HimsBackendConfig`` (per tenant). Auth tokens
live on ``HimsApiToken`` (named, expiring, OpenAI-style). Nothing is read
from or written to ``.env`` for HIMS.
"""
from __future__ import annotations

import base64
import json
import time
from datetime import timedelta
from typing import Any

import httpx
from django.utils import timezone

from . import hims
from .models import HimsApiToken, HimsBackendConfig, Tenant

# Preset expiry options offered by the admin UI (days). 0 = never expires.
EXPIRY_PRESETS_DAYS = (0, 7, 30, 60, 90, 180, 365)

# JWTs that HIMS already rejected (401/403) this process — skip on retry.
_rejected_jwts: set[str] = set()


def jwt_is_expired(token: str, *, leeway_seconds: int = 60) -> bool:
    """True if the JWT ``exp`` claim is past (signature not verified)."""
    try:
        parts = (token or "").strip().split(".")
        if len(parts) < 2:
            return True
        pad = "=" * (-len(parts[1]) % 4)
        payload = json.loads(base64.urlsafe_b64decode(parts[1] + pad).decode("utf-8"))
        exp = payload.get("exp")
        if exp is None:
            return False
        return int(exp) <= int(time.time()) + leeway_seconds
    except Exception:
        return True


def mark_jwt_rejected(token: str) -> None:
    token = (token or "").strip()
    if token:
        _rejected_jwts.add(token)
    hims._cached_jwt = None  # noqa: SLF001


def clear_rejected_jwts() -> None:
    _rejected_jwts.clear()


def get_or_create_config(tenant: Tenant) -> HimsBackendConfig:
    config, _ = HimsBackendConfig.objects.get_or_create(tenant=tenant)
    return config


def get_active_connection(*, tenant: Tenant | None = None) -> HimsBackendConfig | None:
    """Resolve which tenant's HIMS connection to use for runtime API calls."""
    if tenant is not None:
        try:
            return tenant.hims_config
        except HimsBackendConfig.DoesNotExist:
            return HimsBackendConfig.objects.filter(tenant=tenant).first()

    # Prefer a connection that has a usable API token.
    now = timezone.now()
    token_qs = (
        HimsApiToken.objects.filter(revoked_at__isnull=True)
        .select_related("tenant", "tenant__hims_config")
        .order_by("-created_at")
    )
    for row in token_qs.iterator():
        if row.is_expired(now=now):
            continue
        raw = (row.token or "").strip()
        if not raw or jwt_is_expired(raw) or raw in _rejected_jwts:
            continue
        cfg = getattr(row.tenant, "hims_config", None)
        if cfg and (cfg.base_url or "").strip():
            return cfg

    return (
        HimsBackendConfig.objects.exclude(base_url="")
        .order_by("-updated_at")
        .first()
    )


def _token_status(row: HimsApiToken, *, now=None) -> str:
    now = now or timezone.now()
    if row.is_revoked:
        return "revoked"
    if row.is_expired(now=now):
        return "expired"
    raw = (row.token or "").strip()
    if raw and jwt_is_expired(raw):
        return "jwt_expired"
    return "active"


def serialize_token(
    row: HimsApiToken,
    *,
    include_secret: bool = False,
    now=None,
) -> dict[str, Any]:
    now = now or timezone.now()
    status = _token_status(row, now=now)
    data: dict[str, Any] = {
        "id": row.id,
        "name": row.name,
        "token_masked": row.masked_token(),
        "token_prefix": row.token_prefix,
        "expires_at": row.expires_at.isoformat() if row.expires_at else None,
        "never_expires": row.expires_at is None,
        "revoked_at": row.revoked_at.isoformat() if row.revoked_at else None,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "last_used_at": row.last_used_at.isoformat() if row.last_used_at else None,
        "status": status,
        "usable": status == "active",
    }
    if include_secret:
        data["token"] = row.token
    return data


def list_tokens(tenant: Tenant) -> list[dict[str, Any]]:
    now = timezone.now()
    rows = HimsApiToken.objects.filter(tenant=tenant).order_by("-created_at")
    return [serialize_token(row, now=now) for row in rows]


def get_active_db_token(*, tenant: Tenant | None = None) -> str | None:
    """Return the newest usable stored JWT (any tenant if tenant is None).

    Skips revoked / admin-expired rows, JWTs past their ``exp`` claim, and
    tokens HIMS already rejected with 401/403 in this process.
    """
    now = timezone.now()
    qs = HimsApiToken.objects.filter(revoked_at__isnull=True).order_by("-created_at")
    if tenant is not None:
        qs = qs.filter(tenant=tenant)
    for row in qs.iterator():
        if row.is_expired(now=now):
            continue
        raw = (row.token or "").strip()
        if not raw:
            continue
        if raw in _rejected_jwts or jwt_is_expired(raw):
            continue
        HimsApiToken.objects.filter(pk=row.pk).update(last_used_at=now)
        return raw
    return None


def _store_jwt_token(
    tenant: Tenant,
    jwt: str,
    *,
    name: str = "Auto-refreshed",
    expires_in_days: int = 15,
) -> HimsApiToken:
    prefix, suffix = _split_token_display(jwt)
    expires_at = timezone.now() + timedelta(days=expires_in_days)
    row = HimsApiToken.objects.create(
        tenant=tenant,
        name=name[:120],
        token_prefix=prefix,
        token_suffix=suffix,
        token=jwt,
        expires_at=expires_at,
    )
    clear_rejected_jwts()
    return row


def ensure_hims_jwt(*, tenant: Tenant | None = None, force: bool = False) -> str | None:
    """Return a usable JWT, auto-minting via encrypted password when needed."""
    del force  # Cache clearing is handled by the caller; rejected JWTs are skipped below.
    existing = get_active_db_token(tenant=tenant)
    if existing:
        return existing

    cfg = (
        get_or_create_config(tenant)
        if tenant is not None
        else get_active_connection()
    )
    if cfg is None:
        return None

    owner = tenant or cfg.tenant
    password = cfg.get_password()
    if password and (cfg.username or "").strip() and (cfg.base_url or "").strip():
        code, _message, jwt, _meta = _fetch_hims_jwt(
            owner,
            password=password,
            signup_if_missing=False,
        )
        if code == 200 and jwt:
            _store_jwt_token(owner, jwt, name="Auto-refreshed")
            return jwt

    # Last resort: newest revoked row whose underlying JWT is still valid.
    now = timezone.now()
    qs = HimsApiToken.objects.filter(revoked_at__isnull=False).order_by("-created_at")
    if owner is not None:
        qs = qs.filter(tenant=owner)
    for row in qs.iterator():
        raw = (row.token or "").strip()
        if not raw or jwt_is_expired(raw) or raw in _rejected_jwts:
            continue
        row.revoked_at = None
        row.last_used_at = now
        row.save(update_fields=["revoked_at", "last_used_at"])
        clear_rejected_jwts()
        return raw
    return None


def get_public_config(*, tenant: Tenant | None = None) -> dict[str, Any]:
    cfg = get_or_create_config(tenant) if tenant is not None else get_active_connection()
    base = ((cfg.base_url if cfg else "") or "").rstrip("/")
    org = str((cfg.organization_id if cfg else "") or "")
    username = ((cfg.username if cfg else "") or "").strip()
    password_set = bool(cfg and cfg.has_password)
    tokens = list_tokens(tenant) if tenant is not None else []
    active_count = sum(1 for t in tokens if t["usable"])
    return {
        "base_url": base,
        "organization_id": org,
        "username": username,
        "password_set": password_set,
        "hims_configured": bool(base),
        "tokens": tokens,
        "active_token_count": active_count,
        "auth_token_set": active_count > 0,
        "expiry_presets_days": list(EXPIRY_PRESETS_DAYS),
    }


def save_config(tenant: Tenant, payload: dict[str, Any]) -> HimsBackendConfig:
    """Persist HIMS connection fields into the database for this tenant.

    Only keys present in ``payload`` are updated. Password is stored encrypted.
    """
    cfg = get_or_create_config(tenant)
    if "base_url" in payload:
        cfg.base_url = str(payload.get("base_url") or "").strip().rstrip("/")
    if "organization_id" in payload:
        cfg.organization_id = str(payload.get("organization_id") or "").strip() or "1"
    if "username" in payload:
        cfg.username = str(payload.get("username") or "").strip()
    if "password" in payload and payload.get("password") is not None and str(payload.get("password")) != "":
        cfg.set_password(str(payload["password"]))
    cfg.save()
    hims._cached_jwt = None  # noqa: SLF001 — intentional cache clear
    return cfg


def _resolve_expires_at(payload: dict[str, Any]):
    """Parse user expiry: expires_in_days, expires_at ISO, or never."""
    if payload.get("never_expires") in (True, "true", "1", 1):
        return None

    raw_at = payload.get("expires_at")
    if raw_at:
        from django.utils.dateparse import parse_datetime

        parsed = parse_datetime(str(raw_at).strip())
        if parsed is None:
            raise ValueError("expires_at must be a valid ISO datetime")
        if timezone.is_naive(parsed):
            parsed = timezone.make_aware(parsed, timezone.get_current_timezone())
        if parsed <= timezone.now():
            raise ValueError("expires_at must be in the future")
        return parsed

    if "expires_in_days" in payload and payload.get("expires_in_days") is not None:
        try:
            days = int(payload["expires_in_days"])
        except (TypeError, ValueError) as exc:
            raise ValueError("expires_in_days must be an integer") from exc
        if days < 0:
            raise ValueError("expires_in_days cannot be negative")
        if days == 0:
            return None
        return timezone.now() + timedelta(days=days)

    return timezone.now() + timedelta(days=90)


def _split_token_display(token: str) -> tuple[str, str]:
    token = (token or "").strip()
    if len(token) >= 12:
        return token[:8], token[-4:]
    if len(token) >= 6:
        return token[:4], token[-2:]
    return "hims", token[-2:] if token else ""


def _fetch_hims_jwt(
    tenant: Tenant,
    *,
    password: str = "",
    signup_if_missing: bool = True,
    email: str = "chatbot-service@local.dev",
) -> tuple[int, str, str | None, dict[str, Any] | None]:
    """Login to hims-micro using request password or decrypted DB password."""
    cfg = get_or_create_config(tenant)
    base = (cfg.base_url or "").rstrip("/")
    username = (cfg.username or "").strip()
    password = (password or "").strip() or cfg.get_password()

    if not base:
        return 400, "Backend base URL is required. Save settings first.", None, None
    if not username:
        return (
            400,
            "HIMS username is not configured for this tenant.",
            None,
            None,
        )
    if not password:
        return (
            400,
            "Service password is required (enter it once; it is stored encrypted).",
            None,
            None,
        )

    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    try:
        with httpx.Client(timeout=30.0) as client:
            if signup_if_missing:
                client.post(
                    f"{base}/api/v1/accounts/signup/",
                    headers=headers,
                    json={
                        "username": username,
                        "password": password,
                        "confirm_password": password,
                        "first_name": "Chatbot",
                        "last_name": "Service",
                        "email": email,
                        "phone": "9999999999",
                        "gender": "other",
                    },
                )

            login = client.post(
                f"{base}/api/v1/accounts/admin-login-token/",
                headers=headers,
                json={"username": username, "password": password},
            )
            try:
                body = login.json()
            except Exception:
                return (
                    login.status_code or 502,
                    f"HIMS login returned non-JSON: {login.text[:200]}",
                    None,
                    None,
                )

            if login.status_code >= 400 or not isinstance(body, dict):
                msg = (
                    body.get("message")
                    if isinstance(body, dict)
                    else "HIMS login failed"
                )
                return login.status_code or 400, str(msg), None, None

            token = body.get("jwt")
            if not token:
                return 500, "HIMS login OK but no jwt in response", None, None

            meta = {
                "tenant_id": body.get("tenant_id"),
                "user_id": body.get("user_id"),
                "message": body.get("message") or "Logged in Successfully!",
            }
            return 200, "ok", str(token), meta
    except httpx.HTTPError as exc:
        return 502, f"Unable to reach HIMS: {exc}", None, None


def create_token(
    tenant: Tenant,
    payload: dict[str, Any],
    *,
    user=None,
) -> tuple[int, str, dict[str, Any]]:
    """Create a new named HIMS token in the database (OpenAI-style)."""
    name = str(payload.get("name") or "").strip()
    if not name:
        name = f"Token {timezone.now().strftime('%Y-%m-%d %H:%M')}"

    try:
        expires_at = _resolve_expires_at(payload)
    except ValueError as exc:
        return 400, str(exc), get_public_config(tenant=tenant)

    if any(
        key in payload
        for key in ("base_url", "organization_id", "username", "password")
    ):
        save_config(tenant, payload)

    signup = payload.get("signup_if_missing", True)
    if isinstance(signup, str):
        signup = signup.lower() in ("1", "true", "yes")

    # Prefer request password; otherwise decrypt the stored password.
    code, message, jwt, meta = _fetch_hims_jwt(
        tenant,
        password=str(payload.get("password") or ""),
        signup_if_missing=bool(signup),
        email=str(payload.get("email") or "chatbot-service@local.dev"),
    )
    if code != 200 or not jwt:
        return code, message, get_public_config(tenant=tenant)

    prefix, suffix = _split_token_display(jwt)
    row = HimsApiToken.objects.create(
        tenant=tenant,
        name=name[:120],
        token_prefix=prefix,
        token_suffix=suffix,
        token=jwt,
        expires_at=expires_at,
        created_by=user if getattr(user, "is_authenticated", False) else None,
    )
    hims._cached_jwt = None  # noqa: SLF001
    clear_rejected_jwts()

    config = get_public_config(tenant=tenant)
    created = serialize_token(row, include_secret=True)
    config["created_token"] = created
    if meta:
        config["login"] = meta
    return (
        200,
        "API token created. Copy it now — the full value is shown only once.",
        config,
    )


def revoke_token(tenant: Tenant, token_id: int) -> tuple[int, str, dict[str, Any]]:
    try:
        row = HimsApiToken.objects.get(pk=token_id, tenant=tenant)
    except HimsApiToken.DoesNotExist:
        return 404, "Token not found", get_public_config(tenant=tenant)

    if row.revoked_at is None:
        row.revoked_at = timezone.now()
        row.save(update_fields=["revoked_at"])
        hims._cached_jwt = None  # noqa: SLF001

    return 200, "Token revoked", get_public_config(tenant=tenant)


def generate_token(
    *,
    signup_if_missing: bool = True,
    email: str = "chatbot-service@local.dev",
    tenant: Tenant | None = None,
    user=None,
    name: str = "",
    expires_in_days: int | None = 90,
) -> tuple[int, str, dict[str, Any]]:
    if tenant is None:
        return 400, "Tenant is required to store tokens in the database", {}
    payload: dict[str, Any] = {
        "name": name,
        "signup_if_missing": signup_if_missing,
        "email": email,
    }
    if expires_in_days is None or expires_in_days == 0:
        payload["never_expires"] = True
    else:
        payload["expires_in_days"] = expires_in_days
    return create_token(tenant, payload, user=user)
