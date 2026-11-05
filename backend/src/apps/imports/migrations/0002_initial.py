import django.db.models.deletion
import django.db.models.expressions
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('imports', '0001_initial'),
        ('warehouse', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='importbatch',
            name='detected_agency',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='import_batches', to='warehouse.agencydimension'),
        ),
        migrations.AddField(
            model_name='importbatch',
            name='uploaded_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='import_batches', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='tb1requeststagingrow',
            name='agency',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='+', to='warehouse.agencydimension'),
        ),
        migrations.AddField(
            model_name='tb1requeststagingrow',
            name='batch',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='tb1_request_rows', to='imports.importbatch'),
        ),
        migrations.AddField(
            model_name='tb2snapshotstagingrow',
            name='agency',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='+', to='warehouse.agencydimension'),
        ),
        migrations.AddField(
            model_name='tb2snapshotstagingrow',
            name='batch',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='tb2_snapshot_rows', to='imports.importbatch'),
        ),
        migrations.AddField(
            model_name='tb2snapshotstagingrow',
            name='matched_tb1',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='matched_tb2_rows', to='imports.tb1requeststagingrow'),
        ),
        migrations.AddField(
            model_name='tb1requeststagingrow',
            name='matched_tb2',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='matched_tb1_rows', to='imports.tb2snapshotstagingrow'),
        ),
        migrations.AddIndex(
            model_name='importbatch',
            index=models.Index(fields=['status', 'created_at'], name='import_batc_status_b888d9_idx'),
        ),
        migrations.AddIndex(
            model_name='importbatch',
            index=models.Index(fields=['workbook_type', 'reporting_period'], name='import_batc_workboo_b13c05_idx'),
        ),
        migrations.AddIndex(
            model_name='importbatch',
            index=models.Index(fields=['detected_agency', 'reporting_period'], name='import_batc_detecte_de0c12_idx'),
        ),
        migrations.AddConstraint(
            model_name='importbatch',
            constraint=models.CheckConstraint(condition=models.Q(('rows_discovered__gte', django.db.models.expressions.CombinedExpression(models.F('rows_imported'), '+', models.F('rows_rejected')))), name='imports_batch_row_counts_valid'),
        ),
        migrations.AddIndex(
            model_name='tb2snapshotstagingrow',
            index=models.Index(fields=['batch', 'validation_status', 'match_status'], name='stg_tb2_sna_batch_i_3f3275_idx'),
        ),
        migrations.AddIndex(
            model_name='tb2snapshotstagingrow',
            index=models.Index(fields=['agency', 'reporting_period', 'is_current'], name='imports_tb2_scope_current_idx'),
        ),
        migrations.AddIndex(
            model_name='tb2snapshotstagingrow',
            index=models.Index(fields=['agency', 'reference'], name='stg_tb2_sna_agency__02a369_idx'),
        ),
        migrations.AddConstraint(
            model_name='tb2snapshotstagingrow',
            constraint=models.UniqueConstraint(fields=('batch', 'sheet_name', 'source_row'), name='imports_tb2_stage_coordinate_uniq'),
        ),
        migrations.AddConstraint(
            model_name='tb2snapshotstagingrow',
            constraint=models.CheckConstraint(condition=models.Q(('source_row__gte', 1)), name='imports_tb2_stage_positive_row'),
        ),
        migrations.AddIndex(
            model_name='tb1requeststagingrow',
            index=models.Index(fields=['batch', 'validation_status', 'match_status'], name='stg_tb1_req_batch_i_2cbc6d_idx'),
        ),
        migrations.AddIndex(
            model_name='tb1requeststagingrow',
            index=models.Index(fields=['agency', 'reporting_period', 'is_current'], name='imports_tb1_scope_current_idx'),
        ),
        migrations.AddIndex(
            model_name='tb1requeststagingrow',
            index=models.Index(fields=['agency', 'reference'], name='stg_tb1_req_agency__23e168_idx'),
        ),
        migrations.AddConstraint(
            model_name='tb1requeststagingrow',
            constraint=models.UniqueConstraint(fields=('batch', 'sheet_name', 'source_row'), name='imports_tb1_stage_coordinate_uniq'),
        ),
        migrations.AddConstraint(
            model_name='tb1requeststagingrow',
            constraint=models.CheckConstraint(condition=models.Q(('source_row__gte', 1)), name='imports_tb1_stage_positive_row'),
        ),
    ]
