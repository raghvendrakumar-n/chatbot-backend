# Generated manually for FlowTemplate model

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0004_menuoption_step_config"),
    ]

    operations = [
        migrations.CreateModel(
            name="FlowTemplate",
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
                    "key",
                    models.SlugField(
                        help_text="Stable flow key, e.g. book_appointment.",
                        max_length=80,
                        unique=True,
                    ),
                ),
                (
                    "default_option_id",
                    models.PositiveIntegerField(
                        blank=True,
                        help_text="Default menu option id when seeding new tenants (e.g. 1, 20).",
                        null=True,
                        unique=True,
                    ),
                ),
                ("label", models.CharField(max_length=150)),
                (
                    "category",
                    models.CharField(
                        choices=[
                            ("booking", "Booking"),
                            ("enquiry", "Enquiry"),
                            ("info", "Info"),
                            ("manage", "Manage"),
                        ],
                        default="booking",
                        max_length=20,
                    ),
                ),
                ("description", models.TextField(blank=True, default="")),
                ("submit_url", models.CharField(blank=True, default="", max_length=120)),
                ("steps", models.JSONField(blank=True, default=list)),
                (
                    "step_config",
                    models.JSONField(
                        blank=True,
                        default=list,
                        help_text="Default conversation steps for this flow template.",
                    ),
                ),
                ("is_active", models.BooleanField(default=True)),
                ("sort_order", models.PositiveIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "ordering": ["sort_order", "id"],
            },
        ),
    ]
