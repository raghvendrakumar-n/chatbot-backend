"""Database models for multi-tenant chatbot design/configuration.

Every visual and behavioural setting for a tenant's chatbot lives in these
tables, so the frontend can be themed entirely from the database.
"""
from __future__ import annotations

from django.db import models


class Tenant(models.Model):
    """A customer/organisation that owns a branded chatbot."""

    name = models.CharField(max_length=150)
    slug = models.SlugField(
        max_length=80,
        unique=True,
        help_text="Unique key used by the embed/frontend to load this tenant's design.",
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return f"{self.name} ({self.slug})"


class ChatbotDesign(models.Model):
    """All design + behaviour settings for a tenant's chatbot."""

    class LauncherPosition(models.TextChoices):
        BOTTOM_RIGHT = "bottom-right", "Bottom Right"
        BOTTOM_LEFT = "bottom-left", "Bottom Left"

    tenant = models.OneToOneField(
        Tenant, on_delete=models.CASCADE, related_name="design"
    )

    # --- Branding ---
    brand_name = models.CharField(max_length=150, default="")
    bot_name = models.CharField(max_length=80, default="Assistant")
    logo = models.ImageField(upload_to="logos/", blank=True, null=True)
    bot_avatar = models.ImageField(upload_to="avatars/", blank=True, null=True)
    launcher_icon = models.ImageField(upload_to="launchers/", blank=True, null=True)

    # --- Colors (hex, e.g. #0d6efd) ---
    primary_color = models.CharField(max_length=9, default="#0d6efd")
    secondary_color = models.CharField(max_length=9, default="#6c757d")
    header_bg_color = models.CharField(max_length=9, default="#0d6efd")
    header_text_color = models.CharField(max_length=9, default="#ffffff")
    background_color = models.CharField(max_length=9, default="#ffffff")
    user_bubble_color = models.CharField(max_length=9, default="#0d6efd")
    user_text_color = models.CharField(max_length=9, default="#ffffff")
    bot_bubble_color = models.CharField(max_length=9, default="#f1f3f5")
    bot_text_color = models.CharField(max_length=9, default="#212529")

    # --- Typography / layout ---
    font_family = models.CharField(
        max_length=200, default="'Segoe UI', Roboto, Arial, sans-serif"
    )
    launcher_position = models.CharField(
        max_length=20,
        choices=LauncherPosition.choices,
        default=LauncherPosition.BOTTOM_RIGHT,
    )
    header_title = models.CharField(max_length=150, default="")
    header_subtitle = models.CharField(max_length=200, default="")
    input_placeholder = models.CharField(
        max_length=150, default="Type your message..."
    )

    # --- Content / links ---
    privacy_policy_url = models.URLField(blank=True, default="")
    website_url = models.URLField(blank=True, default="")

    # --- Contact ---
    contact_phone = models.CharField(max_length=40, blank=True, default="")
    contact_email = models.EmailField(blank=True, default="")
    contact_whatsapp = models.CharField(max_length=40, blank=True, default="")

    # --- AI / features ---
    ai_enabled = models.BooleanField(default=True)
    voice_enabled = models.BooleanField(default=True)
    tts_enabled = models.BooleanField(default=True)
    ai_system_prompt = models.TextField(blank=True, default="")

    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"Design · {self.tenant.slug}"


class WelcomeMessage(models.Model):
    """Ordered greeting messages shown when the chat opens."""

    design = models.ForeignKey(
        ChatbotDesign, on_delete=models.CASCADE, related_name="welcome_messages"
    )
    order = models.PositiveIntegerField(default=0)
    message = models.CharField(max_length=500)
    show_bot_icon = models.BooleanField(default=False)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self) -> str:
        return f"{self.design.tenant.slug} · {self.message[:30]}"


class MenuOption(models.Model):
    """Tenant chatbot flow (main menu item) — order and labels are editable in admin."""

    class Category(models.TextChoices):
        BOOKING = "booking", "Booking"
        ENQUIRY = "enquiry", "Enquiry"
        INFO = "info", "Info"
        MANAGE = "manage", "Manage"

    design = models.ForeignKey(
        ChatbotDesign, on_delete=models.CASCADE, related_name="menu_options"
    )
    order = models.PositiveIntegerField(default=0)
    option_id = models.PositiveIntegerField(
        help_text="Matches the frontend flow id (e.g. 1=Appointment, 20=Cancel)."
    )
    flow_key = models.SlugField(
        max_length=80,
        blank=True,
        default="",
        help_text="Stable flow key, e.g. book_appointment.",
    )
    label = models.CharField(max_length=150)
    category = models.CharField(
        max_length=20,
        choices=Category.choices,
        default=Category.BOOKING,
    )
    description = models.TextField(blank=True, default="")
    submit_url = models.CharField(max_length=120, blank=True, default="")
    steps = models.JSONField(default=list, blank=True)
    step_config = models.JSONField(
        default=list,
        blank=True,
        help_text="Full configurable conversation steps (messages, choices, inputs).",
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["order", "id"]
        unique_together = [("design", "option_id")]

    def __str__(self) -> str:
        return f"{self.design.tenant.slug} · {self.label}"


class FlowTemplate(models.Model):
    """System-wide flow catalog (default steps stored in DB, editable via Django admin)."""

    class Category(models.TextChoices):
        BOOKING = "booking", "Booking"
        ENQUIRY = "enquiry", "Enquiry"
        INFO = "info", "Info"
        MANAGE = "manage", "Manage"

    key = models.SlugField(
        max_length=80,
        unique=True,
        help_text="Stable flow key, e.g. book_appointment.",
    )
    default_option_id = models.PositiveIntegerField(
        null=True,
        blank=True,
        unique=True,
        help_text="Default menu option id when seeding new tenants (e.g. 1, 20).",
    )
    label = models.CharField(max_length=150)
    category = models.CharField(
        max_length=20,
        choices=Category.choices,
        default=Category.BOOKING,
    )
    description = models.TextField(blank=True, default="")
    submit_url = models.CharField(max_length=120, blank=True, default="")
    steps = models.JSONField(default=list, blank=True)
    step_config = models.JSONField(
        default=list,
        blank=True,
        help_text="Default conversation steps for this flow template.",
    )
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["sort_order", "id"]

    def __str__(self) -> str:
        return self.label

    def to_main_menu_dict(self) -> dict:
        return {
            "id": self.default_option_id,
            "key": self.key,
            "label": self.label,
            "category": self.category,
            "description": self.description,
            "submit_url": self.submit_url,
            "steps": self.steps or [],
        }


class TenantOwner(models.Model):
    """Links a Django user account to the tenant they manage (signup creates both)."""

    user = models.OneToOneField(
        "auth.User", on_delete=models.CASCADE, related_name="tenant_owner"
    )
    tenant = models.OneToOneField(
        Tenant, on_delete=models.CASCADE, related_name="owner"
    )
    full_name = models.CharField(max_length=150, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.user.email} → {self.tenant.slug}"


class HimsBackendConfig(models.Model):
    """Per-tenant HIMS connection settings (URL, org, service username).

    Stored in the database only — not in ``.env``. The service password is
    stored encrypted (Fernet) and decrypted only when minting HIMS tokens.
    """

    tenant = models.OneToOneField(
        Tenant, on_delete=models.CASCADE, related_name="hims_config"
    )
    base_url = models.URLField(
        max_length=300,
        blank=True,
        default="",
        help_text="Root URL of hims-micro, e.g. http://127.0.0.1:8004",
    )
    organization_id = models.CharField(max_length=40, blank=True, default="1")
    username = models.CharField(max_length=150, blank=True, default="")
    password_encrypted = models.TextField(
        blank=True,
        default="",
        help_text="Fernet-encrypted HIMS service password (never store plaintext).",
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "HIMS backend config"
        verbose_name_plural = "HIMS backend configs"

    def __str__(self) -> str:
        return f"HIMS · {self.tenant.slug}"

    @property
    def is_configured(self) -> bool:
        return bool((self.base_url or "").strip())

    @property
    def has_password(self) -> bool:
        return bool((self.password_encrypted or "").strip())

    def set_password(self, plain: str) -> None:
        from .crypto import encrypt_secret

        self.password_encrypted = encrypt_secret(plain)

    def get_password(self) -> str:
        from .crypto import decrypt_secret

        return decrypt_secret(self.password_encrypted)


class HimsApiToken(models.Model):
    """HIMS auth token stored like an OpenAI API key (named, multi, expiring).

    The raw JWT is kept server-side so chatbotb can call hims-micro. The admin
    UI only shows the full value once at create time; afterwards a masked
    prefix/suffix is returned.
    """

    tenant = models.ForeignKey(
        Tenant, on_delete=models.CASCADE, related_name="hims_api_tokens"
    )
    name = models.CharField(
        max_length=120,
        help_text="Label shown in admin, e.g. Production, Staging.",
    )
    token_prefix = models.CharField(
        max_length=16,
        help_text="First characters for masked display (OpenAI-style).",
    )
    token_suffix = models.CharField(
        max_length=8,
        help_text="Last characters for masked display.",
    )
    token = models.TextField(help_text="Raw HIMS JWT used for Authorization Bearer.")
    expires_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When set, chatbotb stops using this token after this time. Null = never.",
    )
    revoked_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        "auth.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="hims_api_tokens_created",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.tenant.slug} · {self.name}"

    @property
    def is_revoked(self) -> bool:
        return self.revoked_at is not None

    def is_expired(self, *, now=None) -> bool:
        from django.utils import timezone

        if self.expires_at is None:
            return False
        return self.expires_at <= (now or timezone.now())

    def is_usable(self, *, now=None) -> bool:
        return not self.is_revoked and not self.is_expired(now=now)

    def masked_token(self) -> str:
        prefix = self.token_prefix or "hims"
        suffix = self.token_suffix or ""
        if suffix:
            return f"{prefix}…{suffix}"
        return f"{prefix}…"
