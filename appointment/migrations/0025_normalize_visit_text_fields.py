from django.db import migrations


def normalize_visit_text_fields(apps, schema_editor):
    Visit = apps.get_model('appointment', 'Visit')
    updates = []

    for visit in Visit.objects.all().iterator():
        changed = False
        for field in ('symptoms', 'diagnosis', 'notes'):
            value = getattr(visit, field)
            if value is not None and value.casefold() == 'none':
                setattr(visit, field, '')
                changed = True
        if changed:
            updates.append(visit)

    if updates:
        Visit.objects.bulk_update(updates, ['symptoms', 'diagnosis', 'notes'])


class Migration(migrations.Migration):

    dependencies = [
        ('appointment', '0024_prescriptionitem_anupana_prescriptionitem_sevan_kaal'),
    ]

    operations = [
        migrations.RunPython(normalize_visit_text_fields, migrations.RunPython.noop),
    ]
