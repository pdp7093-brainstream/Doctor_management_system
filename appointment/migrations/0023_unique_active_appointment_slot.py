from django.db import migrations, models
from django.db.models import Count


BOOKED_STATUSES = ['pending', 'confirmed', 'completed']


def validate_unique_active_slots(apps, schema_editor):
    Appointment = apps.get_model('appointment', 'Appointment')

    duplicate = (
        Appointment.objects
        .filter(is_archived=False, status__in=BOOKED_STATUSES)
        .values('doctor_id', 'appointment_date', 'time_slot')
        .annotate(slot_count=Count('id'))
        .filter(slot_count__gt=1)
        .order_by('appointment_date', 'time_slot')
        .first()
    )

    if duplicate:
        raise ValueError(
            'Cannot add unique appointment slot constraint because duplicate '
            'active appointments already exist for doctor_id={doctor_id}, '
            'appointment_date={appointment_date}, time_slot={time_slot}. '
            'Cancel/archive duplicate appointments first.'
            .format(**duplicate)
        )


class Migration(migrations.Migration):

    dependencies = [
        ('appointment', '0022_patientolddocument'),
    ]

    operations = [
        migrations.RunPython(validate_unique_active_slots, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name='appointment',
            constraint=models.UniqueConstraint(
                fields=('doctor', 'appointment_date', 'time_slot'),
                condition=models.Q(
                    is_archived=False,
                    status__in=BOOKED_STATUSES,
                ),
                name='unique_active_appointment_slot',
            ),
        ),
    ]
