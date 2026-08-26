from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0009_himsbackendconfig"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="himsbackendconfig",
            name="password",
        ),
    ]
