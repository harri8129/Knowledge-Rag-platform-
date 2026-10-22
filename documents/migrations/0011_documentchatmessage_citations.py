from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("documents", "0010_add_document_chat_messages"),
    ]

    operations = [
        migrations.AddField(
            model_name="documentchatmessage",
            name="citations",
            field=models.JSONField(blank=True, default=list),
        ),
    ]
