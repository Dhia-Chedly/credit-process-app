import django.core.validators
import django.db.models.deletion
import uuid
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('imports', '0001_initial'),
    ]

    operations = [
        migrations.RunSQL(
            "CREATE SCHEMA IF NOT EXISTS ingestion;",
            reverse_sql=migrations.RunSQL.noop,
        ),
        migrations.CreateModel(
            name='DataQualityIssue',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('severity', models.CharField(choices=[('info', 'Information'), ('warning', 'Warning'), ('error', 'Error')], max_length=16)),
                ('code', models.CharField(max_length=64, validators=[django.core.validators.RegexValidator(message='Use lowercase letters, numbers, and underscores, starting with a letter.', regex='^[a-z][a-z0-9_]*$')])),
                ('field_name', models.CharField(blank=True, max_length=64)),
                ('message', models.TextField(help_text='Sanitized explanation; source values remain on the protected staged row.')),
                ('details', models.JSONField(blank=True, default=dict, help_text='Structural metadata and whitelisted non-client correction values only; do not copy client names, references, phone numbers, addresses, or comments.')),
                ('batch', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='quality_issues', to='imports.importbatch')),
                ('tb1_row', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='quality_issues', to='imports.tb1requeststagingrow')),
                ('tb2_row', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='quality_issues', to='imports.tb2snapshotstagingrow')),
            ],
            options={
                'db_table': '"ingestion"."stg_data_quality_issue"',
                'ordering': ['-created_at'],
                'indexes': [models.Index(fields=['batch', 'severity'], name='stg_data_qu_batch_i_5745a6_idx'), models.Index(fields=['code'], name='stg_data_qu_code_776fc0_idx')],
                'constraints': [models.UniqueConstraint(fields=('batch', 'tb1_row', 'code', 'field_name'), name='data_quality_tb1_row_issue_uniq'), models.UniqueConstraint(fields=('batch', 'tb2_row', 'code', 'field_name'), name='data_quality_tb2_row_issue_uniq')],
            },
        ),
    ]
