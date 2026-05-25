from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('appointment', '0010_appointment_archived_at_appointment_is_archived'),
    ]

    operations = [
        migrations.AddField(
            model_name='prescriptionitem',
            name='notes',
            field=models.TextField(blank=True, null=True),
        ),
    ]
