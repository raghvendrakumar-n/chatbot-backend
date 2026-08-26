"""Tenant owner signup / login (new tenants register here; keys stay server-side)."""
from __future__ import annotations

from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.db import transaction
from django.utils.text import slugify
from django.views.decorators.csrf import csrf_exempt
from rest_framework.authtoken.models import Token
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from .models import ChatbotDesign, Tenant, TenantOwner
from .serializers import TenantSerializer
from .tenant_defaults import seed_default_design
from .views import envelope


def _user_payload(user: User, owner: TenantOwner) -> dict:
    return {
        "token": Token.objects.get(user=user).key,
        "email": user.email,
        "full_name": owner.full_name,
        "tenant": TenantSerializer(owner.tenant).data,
    }


def _unique_slug(base: str) -> str:
    slug = slugify(base)[:80] or "tenant"
    candidate = slug
    n = 1
    while Tenant.objects.filter(slug=candidate).exists():
        candidate = f"{slug}-{n}"[:80]
        n += 1
    return candidate


def _resolve_user(login_id: str) -> User | None:
    """Find user by username or email (signup uses email as username; admin users may differ)."""
    login_id = login_id.strip().lower()
    if not login_id:
        return None
    user = User.objects.filter(username__iexact=login_id).first()
    if user:
        return user
    return User.objects.filter(email__iexact=login_id).first()


@csrf_exempt
@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
def signup(request: Request) -> Response:
    """Register a new tenant + owner account."""
    org_name = (
        request.data.get("organization_name") or request.data.get("name") or ""
    ).strip()
    full_name = (request.data.get("full_name") or "").strip()
    email = (request.data.get("email") or "").strip().lower()
    password = request.data.get("password") or ""
    confirm = request.data.get("confirm_password") or password

    if not org_name:
        return envelope(400, "Organization name is required", None)
    if not email:
        return envelope(400, "Email is required", None)
    if len(password) < 8:
        return envelope(400, "Password must be at least 8 characters", None)
    if password != confirm:
        return envelope(400, "Passwords do not match", None)
    if User.objects.filter(username=email).exists():
        return envelope(409, "An account with this email already exists", None)

    slug = _unique_slug(request.data.get("slug") or org_name)

    try:
        with transaction.atomic():
            user = User.objects.create_user(
                username=email, email=email, password=password
            )
            tenant = Tenant.objects.create(name=org_name, slug=slug, is_active=True)
            design = ChatbotDesign.objects.create(tenant=tenant, brand_name=org_name)
            seed_default_design(design, org_name, contact_email=email)
            owner = TenantOwner.objects.create(
                user=user, tenant=tenant, full_name=full_name or org_name
            )
            Token.objects.filter(user=user).delete()
            Token.objects.create(user=user)
    except Exception as exc:
        return envelope(500, "Could not create account", str(exc))

    return envelope(201, "Account created", _user_payload(user, owner))


@csrf_exempt
@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
def login(request: Request) -> Response:
    email = (request.data.get("email") or "").strip().lower()
    password = request.data.get("password") or ""

    if not email or not password:
        return envelope(400, "Email and password are required", None)

    user_obj = _resolve_user(email)
    if user_obj is None:
        return envelope(401, "Invalid email or password", None)

    user = authenticate(username=user_obj.username, password=password)
    if user is None:
        return envelope(401, "Invalid email or password", None)

    try:
        owner = user.tenant_owner
    except TenantOwner.DoesNotExist:
        return envelope(403, "This account is not linked to a tenant", None)

    Token.objects.filter(user=user).delete()
    Token.objects.create(user=user)
    return envelope(200, "Login successful", _user_payload(user, owner))


@api_view(["GET"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def me(request: Request) -> Response:
    try:
        owner = request.user.tenant_owner
    except TenantOwner.DoesNotExist:
        return envelope(403, "No tenant linked to this account", None)
    return envelope(
        200,
        "OK",
        {
            "email": request.user.email,
            "full_name": owner.full_name,
            "tenant": TenantSerializer(owner.tenant).data,
        },
    )


@api_view(["POST"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def logout(request: Request) -> Response:
    Token.objects.filter(user=request.user).delete()
    return envelope(200, "Logged out", None)
