"""Drop the removed blockchain app's table (HU-18 replaced by sketch_2d).

The `blockchain` app was deleted; this migration removes its orphaned table and
its rows in django_migrations so the schema is clean. The only FK was
blockchain_modelregistration -> modeling_model3d, so dropping it is safe.
"""

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("modeling", "0002_initial"),
    ]

    operations = [
        migrations.RunSQL(
            sql="DROP TABLE IF EXISTS blockchain_modelregistration CASCADE;",
            reverse_sql=migrations.RunSQL.noop,
        ),
        migrations.RunSQL(
            sql="DELETE FROM django_migrations WHERE app = 'blockchain';",
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
