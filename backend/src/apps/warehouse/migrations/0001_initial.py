import apps.warehouse.fields
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
            "CREATE SCHEMA IF NOT EXISTS warehouse;",
            reverse_sql=migrations.RunSQL.noop,
        ),
        migrations.CreateModel(
            name='ActivityDimension',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('name', models.CharField(max_length=160, unique=True)),
                ('is_active', models.BooleanField(default=True)),
            ],
            options={
                'db_table': '"warehouse"."dim_activity"',
                'ordering': ['name'],
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='CreditTypeDimension',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('name', models.CharField(max_length=160, unique=True)),
                ('is_active', models.BooleanField(default=True)),
            ],
            options={
                'db_table': '"warehouse"."dim_credit_type"',
                'ordering': ['name'],
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='RejectionReasonDimension',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('name', models.CharField(max_length=160, unique=True)),
                ('is_active', models.BooleanField(default=True)),
            ],
            options={
                'db_table': '"warehouse"."dim_rejection_reason"',
                'ordering': ['name'],
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='RequestTypeDimension',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('name', models.CharField(max_length=160, unique=True)),
                ('is_active', models.BooleanField(default=True)),
            ],
            options={
                'db_table': '"warehouse"."dim_request_type"',
                'ordering': ['name'],
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='AgencyDimension',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('name', models.CharField(max_length=120)),
                ('code', models.CharField(blank=True, help_text='Four-digit governed code embedded in request references.', max_length=4, null=True, unique=True, validators=[django.core.validators.RegexValidator('^\\d{4}$', 'Use exactly four digits.')])),
                ('is_active', models.BooleanField(default=True)),
            ],
            options={
                'db_table': '"warehouse"."dim_agency"',
                'ordering': ['name'],
                'constraints': [models.UniqueConstraint(fields=('name',), name='dim_agency_name_uniq')],
            },
        ),
        migrations.CreateModel(
            name='CADimension',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('name', apps.warehouse.fields.EncryptedTextField()),
                ('email', models.EmailField(blank=True, max_length=254)),
                ('is_active', models.BooleanField(default=True)),
                ('agency', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='%(class)s_versions', to='warehouse.agencydimension')),
            ],
            options={
                'db_table': '"warehouse"."dim_ca"',
                'ordering': ['name'],
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='DateDimension',
            fields=[
                ('date_key', models.PositiveIntegerField(editable=False, primary_key=True, serialize=False)),
                ('calendar_date', models.DateField(unique=True)),
                ('day_of_week', models.PositiveSmallIntegerField(editable=False)),
                ('day_of_month', models.PositiveSmallIntegerField(editable=False)),
                ('week_of_year', models.PositiveSmallIntegerField(editable=False)),
                ('month', models.PositiveSmallIntegerField(editable=False)),
                ('month_name', models.CharField(editable=False, max_length=16)),
                ('quarter', models.PositiveSmallIntegerField(editable=False)),
                ('year', models.PositiveSmallIntegerField(editable=False)),
                ('month_start', models.DateField(editable=False)),
                ('quarter_start', models.DateField(editable=False)),
                ('is_weekend', models.BooleanField(editable=False)),
            ],
            options={
                'db_table': '"warehouse"."dim_date"',
                'ordering': ['calendar_date'],
                'indexes': [models.Index(fields=['year', 'month'], name='dim_date_year_392d77_idx')],
                'constraints': [models.CheckConstraint(condition=models.Q(('month__gte', 1), ('month__lte', 12)), name='dim_date_month'), models.CheckConstraint(condition=models.Q(('quarter__gte', 1), ('quarter__lte', 4)), name='dim_date_quarter')],
            },
        ),
        migrations.CreateModel(
            name='GPDimension',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('name', apps.warehouse.fields.EncryptedTextField()),
                ('email', models.EmailField(blank=True, max_length=254)),
                ('is_active', models.BooleanField(default=True)),
                ('agency', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='%(class)s_versions', to='warehouse.agencydimension')),
            ],
            options={
                'db_table': '"warehouse"."dim_gp"',
                'ordering': ['name'],
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='StatusDimension',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('code', models.CharField(max_length=48, unique=True, validators=[django.core.validators.RegexValidator(message='Use lowercase letters, numbers, and underscores, starting with a letter.', regex='^[a-z][a-z0-9_]*$')])),
                ('name', models.CharField(max_length=160)),
                ('is_active', models.BooleanField(default=True)),
                ('pipeline_stage', models.CharField(choices=[('intake', 'Intake'), ('waiting_visit', 'Waiting for visit'), ('waiting_decision', 'Waiting for decision'), ('waiting_disbursement', 'Waiting for disbursement'), ('completed', 'Completed')], max_length=32)),
                ('is_terminal', models.BooleanField(default=False)),
                ('is_funded', models.BooleanField(default=False)),
                ('is_rejected', models.BooleanField(default=False)),
            ],
            options={
                'db_table': '"warehouse"."dim_status"',
                'ordering': ['name'],
                'indexes': [models.Index(fields=['pipeline_stage', 'is_active'], name='dim_status_pipelin_91d2e0_idx')],
                'constraints': [models.CheckConstraint(condition=models.Q(('is_funded', True), ('is_rejected', True), _negated=True), name='dim_status_single_outcome'), models.CheckConstraint(condition=models.Q(models.Q(('is_funded', False), ('is_rejected', False)), ('is_terminal', True), _connector='OR'), name='dim_status_outcome_terminal')],
            },
        ),
        migrations.CreateModel(
            name='FactCreditRequest',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('reference', models.CharField(blank=True, db_index=True, help_text='Canonical governed request reference for operational display and lookup.', max_length=32)),
                ('missing_from_latest_tb2_period', models.DateField(blank=True, help_text='Reporting month of the latest complete TB2 submission in which this dossier was absent; it does not change the business status.', null=True)),
                ('amount', models.DecimalField(blank=True, decimal_places=3, max_digits=18, null=True)),
                ('activity', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='requests', to='warehouse.activitydimension')),
                ('agency', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='requests', to='warehouse.agencydimension')),
                ('ca_caa', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='ca_caa_requests', to='warehouse.cadimension')),
                ('credit_type', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='requests', to='warehouse.credittypedimension')),
                ('current_tb1_row', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='controlling_facts', to='imports.tb1requeststagingrow')),
                ('current_tb2_row', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='controlling_facts', to='imports.tb2snapshotstagingrow')),
                ('disbursement_date', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='+', to='warehouse.datedimension')),
                ('gp_assignment_date', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='+', to='warehouse.datedimension')),
                ('reception_date', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='+', to='warehouse.datedimension')),
                ('rejection_date', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='+', to='warehouse.datedimension')),
                ('request_date', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='+', to='warehouse.datedimension')),
                ('visit_date', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='+', to='warehouse.datedimension')),
                ('gp', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='gp_requests', to='warehouse.gpdimension')),
                ('rejection_reason', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='requests', to='warehouse.rejectionreasondimension')),
                ('request_type', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='requests', to='warehouse.requesttypedimension')),
                ('status', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='requests', to='warehouse.statusdimension')),
            ],
            options={
                'db_table': '"warehouse"."fact_credit_request"',
                'ordering': ['-request_date_id', 'agency_id', 'reference'],
            },
        ),
        migrations.CreateModel(
            name='CreditRequestStatusHistory',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('source_tb1_row', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='status_history_entries', to='imports.tb1requeststagingrow')),
                ('source_tb2_row', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='status_history_entries', to='imports.tb2snapshotstagingrow')),
                ('effective_date', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='+', to='warehouse.datedimension')),
                ('credit_request', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='status_history', to='warehouse.factcreditrequest')),
                ('status', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='+', to='warehouse.statusdimension')),
            ],
            options={
                'db_table': '"warehouse"."credit_request_status_history"',
                'ordering': ['credit_request_id', 'effective_date_id', 'created_at', 'id'],
            },
        ),
        migrations.AddIndex(
            model_name='cadimension',
            index=models.Index(fields=['agency', 'is_active'], name='dim_ca_agency__cb6d86_idx'),
        ),
        migrations.AddIndex(
            model_name='gpdimension',
            index=models.Index(fields=['agency', 'is_active'], name='dim_gp_agency__a38bf1_idx'),
        ),
        migrations.AddIndex(
            model_name='factcreditrequest',
            index=models.Index(fields=['request_date', 'agency'], name='fact_credit_request_56817a_idx'),
        ),
        migrations.AddIndex(
            model_name='factcreditrequest',
            index=models.Index(fields=['status', 'request_date'], name='fact_credit_status__9332e4_idx'),
        ),
        migrations.AddIndex(
            model_name='factcreditrequest',
            index=models.Index(fields=['gp', 'request_date'], name='fact_credit_gp_id_0b2706_idx'),
        ),
        migrations.AddIndex(
            model_name='factcreditrequest',
            index=models.Index(fields=['ca_caa', 'request_date'], name='fact_credit_ca_caa__839990_idx'),
        ),
        migrations.AddConstraint(
            model_name='factcreditrequest',
            constraint=models.UniqueConstraint(fields=('agency', 'reference'), name='fact_request_agency_reference_uniq'),
        ),
        migrations.AddConstraint(
            model_name='factcreditrequest',
            constraint=models.CheckConstraint(condition=models.Q(('amount__isnull', True), ('amount__gte', 0), _connector='OR'), name='fact_request_amount_nonnegative'),
        ),
        migrations.AddConstraint(
            model_name='factcreditrequest',
            constraint=models.CheckConstraint(condition=models.Q(('disbursement_date__isnull', True), ('rejection_date__isnull', True), _connector='OR'), name='fact_request_single_outcome_date'),
        ),
        migrations.AddIndex(
            model_name='creditrequeststatushistory',
            index=models.Index(fields=['credit_request', 'effective_date'], name='credit_requ_credit__68727d_idx'),
        ),
        migrations.AddIndex(
            model_name='creditrequeststatushistory',
            index=models.Index(fields=['status', 'effective_date'], name='credit_requ_status__7c3eb0_idx'),
        ),
        migrations.AddConstraint(
            model_name='creditrequeststatushistory',
            constraint=models.CheckConstraint(condition=models.Q(models.Q(('source_tb1_row__isnull', False), ('source_tb2_row__isnull', True)), models.Q(('source_tb1_row__isnull', True), ('source_tb2_row__isnull', False)), _connector='OR'), name='status_history_exactly_one_source'),
        ),
    ]
