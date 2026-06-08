import re

from django.db import migrations, models


def seed_bill_sequence(apps, schema_editor):
    Bill = apps.get_model('billing', 'Bill')
    BillSequence = apps.get_model('billing', 'BillSequence')

    max_bill_number = 0
    pattern = re.compile(r'^BILL-(\d+)$')

    for bill_number in Bill.objects.values_list('bill_number', flat=True):
        match = pattern.match(bill_number or '')
        if match:
            max_bill_number = max(max_bill_number, int(match.group(1)))

    BillSequence.objects.update_or_create(
        name='bill_numbers',
        defaults={'last_number': max_bill_number},
    )


def remove_bill_sequence(apps, schema_editor):
    BillSequence = apps.get_model('billing', 'BillSequence')
    BillSequence.objects.filter(name='bill_numbers').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('billing', '0005_bill_archived_at_bill_is_archived'),
    ]

    operations = [
        migrations.CreateModel(
            name='BillSequence',
            fields=[
                ('name', models.CharField(max_length=32, primary_key=True, serialize=False)),
                ('last_number', models.PositiveIntegerField(default=0)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
        ),
        migrations.RunPython(seed_bill_sequence, remove_bill_sequence),
    ]
