from django.db import migrations


def normalize_bill_notes(apps, schema_editor):
    Bill = apps.get_model('billing', 'Bill')
    bills_to_update = []

    for bill in Bill.objects.all().iterator():
        if bill.notes is None:
            continue
        cleaned_notes = bill.notes.strip()
        if not cleaned_notes or cleaned_notes.casefold() == 'none':
            bill.notes = ''
            bills_to_update.append(bill)

    if bills_to_update:
        Bill.objects.bulk_update(bills_to_update, ['notes'])


class Migration(migrations.Migration):

    dependencies = [
        ('billing', '0006_billsequence'),
    ]

    operations = [
        migrations.RunPython(normalize_bill_notes, migrations.RunPython.noop),
    ]