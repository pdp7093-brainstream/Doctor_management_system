# Generated during settings cleanup.

from django.db import migrations


def copy_doctor_settings_to_clinic(apps, schema_editor):
    OldClinicSettings = apps.get_model('doctor', 'ClinicSettings')
    ClinicSettings = apps.get_model('clinic', 'ClinicSettings')

    old_settings = OldClinicSettings.objects.order_by('id').first()
    if not old_settings:
        return

    clinic, _ = ClinicSettings.objects.get_or_create(pk=1)

    field_map = {
        'clinic_name': 'clinic_name',
        'address': 'address',
        'phone': 'phone',
        'email': 'email',
        'opening_time': 'start_time',
        'closing_time': 'end_time',
        'lunch_start': 'lunch_start',
        'lunch_end': 'lunch_end',
        'footer_note': 'bill_footer_note',
    }

    for old_field, new_field in field_map.items():
        value = getattr(old_settings, old_field, None)
        if value:
            max_length = getattr(ClinicSettings._meta.get_field(new_field), 'max_length', None)
            if max_length and isinstance(value, str):
                value = value[:max_length]
            setattr(clinic, new_field, value)

    if getattr(old_settings, 'clinic_logo', None) and old_settings.clinic_logo.name:
        clinic.logo = old_settings.clinic_logo.name

    clinic.save()


class Migration(migrations.Migration):

    dependencies = [
        ('clinic', '0002_alter_clinicsettings_options_and_more'),
        ('doctor', '0006_clinicsettings'),
    ]

    operations = [
        migrations.RunPython(copy_doctor_settings_to_clinic, migrations.RunPython.noop),
        migrations.DeleteModel(
            name='ClinicSettings',
        ),
    ]
