from django.db import migrations, models


def mark_current_booking_doctor(apps, schema_editor):
    InnerMember = apps.get_model('doctor', 'InnerMember')
    first_doctor = InnerMember.objects.filter(role='doctor').order_by('pk').first()
    if first_doctor:
        first_doctor.is_default_doctor = True
        first_doctor.save(update_fields=['is_default_doctor'])


class Migration(migrations.Migration):
    dependencies = [
        ('doctor', '0013_innermember_profile_picture'),
    ]

    operations = [
        migrations.AddField(
            model_name='innermember',
            name='is_default_doctor',
            field=models.BooleanField(default=False),
        ),
        migrations.RunPython(mark_current_booking_doctor, migrations.RunPython.noop),
    ]