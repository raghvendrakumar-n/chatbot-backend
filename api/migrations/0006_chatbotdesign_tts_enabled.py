from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0005_flowtemplate"),
    ]

    operations = [
        migrations.AddField(
            model_name="chatbotdesign",
            name="tts_enabled",
            field=models.BooleanField(default=False),
        ),
    ]
