from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0010_remove_himsbackendconfig_password"),
    ]

    operations = [
        migrations.AddField(
            model_name="himsbackendconfig",
            name="password_encrypted",
            field=models.TextField(
                blank=True,
                default="",
                help_text="Fernet-encrypted HIMS service password (never store plaintext).",
            ),
        ),
    ]
