from django.db import migrations, models
import django.db.models.deletion


def seed_hims_config_from_env(apps, schema_editor):
    """Copy legacy .env HIMS_* values into DB for every existing tenant."""
    import os
    from pathlib import Path

    from django.conf import settings

    Tenant = apps.get_model("api", "Tenant")
    HimsBackendConfig = apps.get_model("api", "HimsBackendConfig")

    env_path = Path(settings.BASE_DIR) / ".env"
    values = {
        "HIMS_BASE_URL": os.getenv("HIMS_BASE_URL", "") or "",
        "HIMS_ORGANIZATION_ID": os.getenv("HIMS_ORGANIZATION_ID", "") or "1",
        "HIMS_USERNAME": os.getenv("HIMS_USERNAME", "") or "",
        "HIMS_PASSWORD": os.getenv("HIMS_PASSWORD", "") or "",
    }
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key = key.strip()
            if key in values:
                values[key] = val.strip()

    base = (values["HIMS_BASE_URL"] or "").rstrip("/")
    if not base and not values["HIMS_USERNAME"]:
        return

    for tenant in Tenant.objects.all():
        HimsBackendConfig.objects.update_or_create(
            tenant_id=tenant.id,
            defaults={
                "base_url": base,
                "organization_id": values["HIMS_ORGANIZATION_ID"] or "1",
                "username": values["HIMS_USERNAME"] or "",
                "password": values["HIMS_PASSWORD"] or "",
            },
        )


def unseed_hims_config(apps, schema_editor):
    HimsBackendConfig = apps.get_model("api", "HimsBackendConfig")
    HimsBackendConfig.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0008_himsapitoken"),
    ]

    operations = [
        migrations.CreateModel(
            name="HimsBackendConfig",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "base_url",
                    models.URLField(
                        blank=True,
                        default="",
                        help_text="Root URL of hims-micro, e.g. http://127.0.0.1:8004",
                        max_length=300,
                    ),
                ),
                (
                    "organization_id",
                    models.CharField(blank=True, default="1", max_length=40),
                ),
                (
                    "username",
                    models.CharField(blank=True, default="", max_length=150),
                ),
                (
                    "password",
                    models.CharField(blank=True, default="", max_length=255),
                ),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "tenant",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="hims_config",
                        to="api.tenant",
                    ),
                ),
            ],
            options={
                "verbose_name": "HIMS backend config",
                "verbose_name_plural": "HIMS backend configs",
            },
        ),
        migrations.RunPython(seed_hims_config_from_env, unseed_hims_config),
    ]
