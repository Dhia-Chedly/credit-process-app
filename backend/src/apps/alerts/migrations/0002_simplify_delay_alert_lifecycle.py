from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("alerts", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="delayalert",
            name="state",
            field=models.CharField(
                choices=[("new", "Nouveau"), ("escalated", "Escaladé")],
                default="new",
                max_length=16,
            ),
        ),
        migrations.RemoveField(model_name="delayalert", name="operator_note"),
        migrations.RemoveField(model_name="delayalert", name="resolved_at"),
        migrations.RemoveField(model_name="delayalert", name="reviewed_at"),
        migrations.RemoveField(model_name="delayalert", name="reviewed_by"),
    ]
