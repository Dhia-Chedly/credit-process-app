import uuid
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.RunSQL(
            "CREATE SCHEMA IF NOT EXISTS auth;",
            reverse_sql=migrations.RunSQL.noop,
        ),
        migrations.CreateModel(
            name='User',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('username', models.CharField(max_length=150, unique=True)),
                ('password', models.CharField(db_column='password_hash', max_length=128)),
                ('is_active', models.BooleanField(default=True)),
                ('is_reference_admin', models.BooleanField(default=False, help_text='May manage governed operational reference data.')),
                ('auth_version', models.PositiveIntegerField(default=1, editable=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'db_table': '"auth"."users"',
                'ordering': ['username'],
            },
        ),
    ]
