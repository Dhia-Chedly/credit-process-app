import apps.imports.models
import django.core.validators
import uuid
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.RunSQL(
            "CREATE SCHEMA IF NOT EXISTS ingestion;",
            reverse_sql=migrations.RunSQL.noop,
        ),
        migrations.CreateModel(
            name='ImportBatch',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('original_filename', models.CharField(max_length=255)),
                ('source_file', models.FileField(max_length=500, upload_to=apps.imports.models.import_file_path)),
                ('workbook_type', models.CharField(choices=[('unknown', 'Unknown'), ('tb1', 'TB1 - credit requests'), ('tb2', 'TB2 - outstanding loans')], default='unknown', max_length=16)),
                ('status', models.CharField(choices=[('uploaded', 'Uploaded'), ('queued', 'Queued'), ('processing', 'Processing'), ('completed', 'Completed'), ('partial', 'Completed with quarantined rows'), ('failed', 'Failed')], default='uploaded', max_length=16)),
                ('checksum_sha256', models.CharField(max_length=64, unique=True, validators=[django.core.validators.RegexValidator(message='Enter a lowercase hexadecimal SHA-256 checksum.', regex='^[0-9a-f]{64}$')])),
                ('file_size', models.PositiveBigIntegerField(help_text='Uploaded file size in bytes.')),
                ('reporting_period', models.DateField(blank=True, help_text='First calendar day of the reporting month when it can be detected.', null=True)),
                ('sheet_name', models.CharField(blank=True, max_length=255)),
                ('rows_discovered', models.PositiveIntegerField(default=0)),
                ('rows_imported', models.PositiveIntegerField(default=0)),
                ('rows_rejected', models.PositiveIntegerField(default=0)),
                ('started_at', models.DateTimeField(blank=True, null=True)),
                ('finished_at', models.DateTimeField(blank=True, null=True)),
                ('error_message', models.TextField(blank=True, help_text='Sanitized failure summary; never include workbook cell values.')),
            ],
            options={
                'db_table': '"ingestion"."import_batch"',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='TB1RequestStagingRow',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('sheet_name', models.CharField(default='', max_length=255)),
                ('source_row', models.PositiveIntegerField()),
                ('reporting_period', models.DateField(blank=True, help_text='First day of the source row reporting month when it can be determined.', null=True)),
                ('is_current', models.BooleanField(default=True, help_text='False when a newer import replaces this agency, period, and workbook scope.')),
                ('row_hash', models.CharField(default='', max_length=64, validators=[django.core.validators.RegexValidator(message='Enter a lowercase hexadecimal SHA-256 checksum.', regex='^[0-9a-f]{64}$')])),
                ('reference', models.CharField(blank=True, db_index=True, help_text='Canonical governed request reference, retained for operational lookup.', max_length=32)),
                ('correction_values', models.JSONField(blank=True, default=dict, help_text='Controlled non-client workbook values used only to display correction rows; ignored client/comment fields are prohibited.')),
                ('validation_status', models.CharField(choices=[('pending', 'Pending'), ('valid', 'Valid'), ('invalid', 'Invalid')], default='pending', max_length=16)),
                ('match_status', models.CharField(choices=[('unmatched', 'Unmatched'), ('matched', 'Matched'), ('blocked', 'Blocked')], default='unmatched', max_length=16)),
                ('amount', models.DecimalField(blank=True, decimal_places=3, max_digits=18, null=True)),
                ('credit_type_name', models.CharField(blank=True, max_length=120)),
                ('request_type_name', models.CharField(blank=True, max_length=120)),
                ('activity_name', models.CharField(blank=True, max_length=120)),
                ('request_date', models.DateField(blank=True, null=True)),
            ],
            options={
                'db_table': '"ingestion"."stg_tb1_request_row"',
                'ordering': ['batch_id', 'sheet_name', 'source_row'],
            },
        ),
        migrations.CreateModel(
            name='TB2SnapshotStagingRow',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('sheet_name', models.CharField(default='', max_length=255)),
                ('source_row', models.PositiveIntegerField()),
                ('reporting_period', models.DateField(blank=True, help_text='First day of the source row reporting month when it can be determined.', null=True)),
                ('is_current', models.BooleanField(default=True, help_text='False when a newer import replaces this agency, period, and workbook scope.')),
                ('row_hash', models.CharField(default='', max_length=64, validators=[django.core.validators.RegexValidator(message='Enter a lowercase hexadecimal SHA-256 checksum.', regex='^[0-9a-f]{64}$')])),
                ('reference', models.CharField(blank=True, db_index=True, help_text='Canonical governed request reference, retained for operational lookup.', max_length=32)),
                ('correction_values', models.JSONField(blank=True, default=dict, help_text='Controlled non-client workbook values used only to display correction rows; ignored client/comment fields are prohibited.')),
                ('validation_status', models.CharField(choices=[('pending', 'Pending'), ('valid', 'Valid'), ('invalid', 'Invalid')], default='pending', max_length=16)),
                ('match_status', models.CharField(choices=[('unmatched', 'Unmatched'), ('matched', 'Matched'), ('blocked', 'Blocked')], default='unmatched', max_length=16)),
                ('amount', models.DecimalField(blank=True, decimal_places=3, max_digits=18, null=True)),
                ('gp_name', models.CharField(blank=True, max_length=160)),
                ('ca_name', models.CharField(blank=True, max_length=160)),
                ('received_at_agency_date', models.DateField(blank=True, null=True)),
                ('assigned_to_gp_date', models.DateField(blank=True, null=True)),
                ('visit_date', models.DateField(blank=True, null=True)),
                ('disbursement_date', models.DateField(blank=True, null=True)),
                ('rejection_date', models.DateField(blank=True, null=True)),
                ('rejection_reason', models.CharField(blank=True, max_length=160)),
            ],
            options={
                'db_table': '"ingestion"."stg_tb2_snapshot_row"',
                'ordering': ['batch_id', 'sheet_name', 'source_row'],
            },
        ),
    ]
