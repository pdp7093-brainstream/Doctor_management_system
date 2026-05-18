# Generated during appointment query optimization.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('appointment', '0005_remove_appointment_created_at_and_more'),
    ]

    operations = [
        migrations.AddIndex(
            model_name='appointment',
            index=models.Index(fields=['appointment_date', 'time_slot'], name='appt_date_time_idx'),
        ),
        migrations.AddIndex(
            model_name='appointment',
            index=models.Index(fields=['appointment_date', 'status'], name='appt_date_status_idx'),
        ),
        migrations.AddIndex(
            model_name='appointment',
            index=models.Index(fields=['status'], name='appt_status_idx'),
        ),
        migrations.AddIndex(
            model_name='appointment',
            index=models.Index(fields=['doctor', 'appointment_date'], name='appt_doctor_date_idx'),
        ),
    ]
