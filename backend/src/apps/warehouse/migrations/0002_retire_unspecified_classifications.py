from django.db import migrations

RETIRED_LABELS = ("Non spécifié", "Unspecified")


def retire_unspecified_classifications(apps, _schema_editor):
    FactCreditRequest = apps.get_model("warehouse", "FactCreditRequest")
    CreditTypeDimension = apps.get_model("warehouse", "CreditTypeDimension")
    RequestTypeDimension = apps.get_model("warehouse", "RequestTypeDimension")

    FactCreditRequest.objects.filter(credit_type__name__in=RETIRED_LABELS).update(credit_type=None)
    FactCreditRequest.objects.filter(request_type__name__in=RETIRED_LABELS).update(
        request_type=None
    )
    CreditTypeDimension.objects.filter(name__in=RETIRED_LABELS).update(is_active=False)
    RequestTypeDimension.objects.filter(name__in=RETIRED_LABELS).update(is_active=False)


class Migration(migrations.Migration):
    dependencies = [("warehouse", "0001_initial")]

    operations = [
        migrations.RunPython(retire_unspecified_classifications, migrations.RunPython.noop)
    ]
