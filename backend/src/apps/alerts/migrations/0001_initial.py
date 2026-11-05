import uuid
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('warehouse', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.RunSQL(
            "CREATE SCHEMA IF NOT EXISTS alerts;",
            reverse_sql=migrations.RunSQL.noop,
        ),
        migrations.CreateModel(
            name='DelayAlert',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('rule', models.CharField(choices=[('reception_blocked', 'Réception bloquée'), ('visit_blocked', 'Visite bloquée')], max_length=32)),
                ('state', models.CharField(choices=[('new', 'Nouveau'), ('reviewed', 'Consulté'), ('escalated', 'Escaladé'), ('resolved', 'Résolu')], default='new', max_length=16)),
                ('reporting_period', models.DateField()),
                ('started_on', models.DateField()),
                ('responsible_role', models.CharField(max_length=8)),
                ('responsible_name', models.CharField(blank=True, max_length=160)),
                ('reviewed_at', models.DateTimeField(blank=True, null=True)),
                ('operator_note', models.TextField(blank=True)),
                ('resolved_at', models.DateTimeField(blank=True, null=True)),
                ('agency', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='delay_alerts', to='warehouse.agencydimension')),
                ('credit_request', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='delay_alerts', to='warehouse.factcreditrequest')),
                ('reviewed_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='reviewed_delay_alerts', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': '"alerts"."delay_alert"',
                'ordering': ['state', '-reporting_period', 'agency__name', 'started_on'],
                'indexes': [models.Index(fields=['agency', 'state'], name='delay_alert_agency__d19b51_idx'), models.Index(fields=['reporting_period', 'state'], name='delay_alert_reporti_635548_idx')],
                'constraints': [models.UniqueConstraint(fields=('credit_request', 'rule'), name='delay_alert_request_rule_uniq')],
            },
        ),
    ]
