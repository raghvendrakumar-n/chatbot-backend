from django.db import migrations, models


def enable_tts_for_existing(apps, schema_editor):
    ChatbotDesign = apps.get_model("api", "ChatbotDesign")
    ChatbotDesign.objects.filter(tts_enabled=False).update(tts_enabled=True)


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0006_chatbotdesign_tts_enabled"),
    ]

    operations = [
        migrations.AlterField(
            model_name="chatbotdesign",
            name="tts_enabled",
            field=models.BooleanField(default=True),
        ),
        migrations.RunPython(enable_tts_for_existing, migrations.RunPython.noop),
    ]
