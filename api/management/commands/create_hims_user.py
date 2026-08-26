"""Create a HIMS service user and store connection + token in the database.

Uses hims-micro APIs:
  POST /api/v1/accounts/signup/
  POST /api/v1/accounts/admin-login-token/

Usage:
    python manage.py create_hims_user --tenant-slug nu-hospitals
    python manage.py create_hims_user --tenant-slug nu-hospitals --username chatbot_service
"""
from __future__ import annotations

from datetime import timedelta

import httpx
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from api.models import HimsApiToken, HimsBackendConfig, Tenant


DEFAULT_USERNAME = "chatbot_service"
DEFAULT_PASSWORD = "ChatbotService@123"


class Command(BaseCommand):
    help = "Create HIMS service user and save connection + token to the database"

    def add_arguments(self, parser):
        parser.add_argument(
            "--tenant-slug",
            required=True,
            help="Chatbot tenant slug that owns the HIMS config",
        )
        parser.add_argument(
            "--username",
            default=DEFAULT_USERNAME,
            help="HIMS username to create / login as",
        )
        parser.add_argument(
            "--password",
            default=DEFAULT_PASSWORD,
            help="HIMS password",
        )
        parser.add_argument(
            "--base-url",
            default="http://127.0.0.1:8004",
            help="hims-micro base URL",
        )
        parser.add_argument(
            "--organization-id",
            default="1",
            help="HIMS organization id",
        )
        parser.add_argument(
            "--skip-signup",
            action="store_true",
            help="Do not call signup; only login and store token",
        )
        parser.add_argument(
            "--email",
            default="chatbot-service@local.dev",
            help="Email used on signup",
        )
        parser.add_argument(
            "--token-name",
            default="CLI token",
            help="Label for the stored API token",
        )
        parser.add_argument(
            "--expires-in-days",
            type=int,
            default=90,
            help="Token lifetime in days (0 = never)",
        )

    def handle(self, *args, **options):
        try:
            tenant = Tenant.objects.get(slug=str(options["tenant_slug"]).strip())
        except Tenant.DoesNotExist as exc:
            raise CommandError(
                f"Unknown tenant slug: {options['tenant_slug']}"
            ) from exc

        base = str(options["base_url"]).rstrip("/")
        username = str(options["username"]).strip().lower()
        password = str(options["password"])
        org_id = str(options["organization_id"]).strip() or "1"
        email = str(options["email"]).strip()

        if not username or not password:
            raise CommandError("username and password are required")

        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        with httpx.Client(timeout=30.0) as client:
            if not options["skip_signup"]:
                signup_url = f"{base}/api/v1/accounts/signup/"
                self.stdout.write(f"Signup -> {signup_url}")
                signup = client.post(
                    signup_url,
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
                try:
                    signup_body = signup.json()
                except Exception:
                    signup_body = {"raw": signup.text[:300]}

                msg = (
                    signup_body.get("message")
                    if isinstance(signup_body, dict)
                    else str(signup_body)
                )
                if signup.status_code >= 400 or (
                    isinstance(signup_body, dict)
                    and int(signup_body.get("status") or 0) >= 400
                ):
                    if "already exists" in str(msg).lower():
                        self.stdout.write(self.style.WARNING(f"Signup skipped: {msg}"))
                    else:
                        raise CommandError(
                            f"Signup failed ({signup.status_code}): {signup_body}"
                        )
                else:
                    self.stdout.write(self.style.SUCCESS(f"Signup OK: {msg}"))

            login_url = f"{base}/api/v1/accounts/admin-login-token/"
            self.stdout.write(f"Login -> {login_url}")
            login = client.post(
                login_url,
                headers=headers,
                json={"username": username, "password": password},
            )
            try:
                login_body = login.json()
            except Exception as exc:
                raise CommandError(
                    f"Login returned non-JSON ({login.status_code}): {login.text[:300]}"
                ) from exc

            if login.status_code >= 400 or not isinstance(login_body, dict):
                raise CommandError(f"Login failed ({login.status_code}): {login_body}")

            token = login_body.get("jwt")
            if not token:
                raise CommandError(f"Login OK but no jwt in response: {login_body}")

        cfg, _ = HimsBackendConfig.objects.update_or_create(
            tenant=tenant,
            defaults={
                "base_url": base,
                "organization_id": org_id,
                "username": username,
            },
        )
        self.stdout.write(self.style.SUCCESS(f"Saved HIMS connection for {tenant.slug}"))

        days = int(options["expires_in_days"])
        expires_at = None if days <= 0 else timezone.now() + timedelta(days=days)
        jwt = str(token)
        prefix = jwt[:8] if len(jwt) >= 12 else jwt[:4]
        suffix = jwt[-4:] if len(jwt) >= 12 else jwt[-2:]
        row = HimsApiToken.objects.create(
            tenant=tenant,
            name=str(options["token_name"])[:120],
            token_prefix=prefix,
            token_suffix=suffix,
            token=jwt,
            expires_at=expires_at,
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"Stored API token id={row.id} ({row.masked_token()}) "
                f"tenant_id={login_body.get('tenant_id')} user_id={login_body.get('user_id')}"
            )
        )
        self.stdout.write(f"Config id={cfg.id} base_url={cfg.base_url}")
