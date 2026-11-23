from django.db import migrations


def clear_none_phones(apps, schema_editor):
    Patient = apps.get_model('accounts', 'Patient')
    FamilyMember = apps.get_model('accounts', 'FamilyMember')
    Patient.objects.filter(phone__in=['None', 'none']).update(phone=None)
    FamilyMember.objects.filter(phone__in=['None', 'none']).update(phone=None)


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0011_case_no'),
    ]

    operations = [
        migrations.RunPython(clear_none_phones, migrations.RunPython.noop),
    ]
