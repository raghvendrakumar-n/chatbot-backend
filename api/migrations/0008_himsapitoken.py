from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("api", "0007_alter_chatbotdesign_tts_enabled"),
    ]

    operations = [
        migrations.CreateModel(
            name="HimsApiToken",
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
                    "name",
                    models.CharField(
                        help_text="Label shown in admin, e.g. Production, Staging.",
                        max_length=120,
                    ),
                ),
                (
                    "token_prefix",
                    models.CharField(
                        help_text="First characters for masked display (OpenAI-style).",
                        max_length=16,
                    ),
                ),
                (
                    "token_suffix",
                    models.CharField(
                        help_text="Last characters for masked display.",
                        max_length=8,
                    ),
                ),
                (
                    "token",
                    models.TextField(
                        help_text="Raw HIMS JWT used for Authorization Bearer."
                    ),
                ),
                (
                    "expires_at",
                    models.DateTimeField(
                        blank=True,
                        help_text="When set, chatbotb stops using this token after this time. Null = never.",
                        null=True,
                    ),
                ),
                ("revoked_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("last_used_at", models.DateTimeField(blank=True, null=True)),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="hims_api_tokens_created",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "tenant",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="hims_api_tokens",
                        to="api.tenant",
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
    ]
