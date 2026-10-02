from django.db import migrations


def drop_orphan_auto_generated(apps, schema_editor):
    """Remove the stray crm_task.auto_generated column left behind when the
    Category-1 follow-up feature was reverted. Guarded so it is a no-op on
    fresh databases where the column was never created."""
    conn = schema_editor.connection
    cols = [c.name for c in conn.introspection.get_table_description(conn.cursor(), "crm_task")]
    if "auto_generated" in cols:
        schema_editor.execute("ALTER TABLE crm_task DROP COLUMN auto_generated")


class Migration(migrations.Migration):

    dependencies = [
        ("crm", "0015_leadcomment"),
    ]

    operations = [
        migrations.RunPython(drop_orphan_auto_generated, migrations.RunPython.noop),
    ]
