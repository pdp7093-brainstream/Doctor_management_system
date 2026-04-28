

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('appointment', '0003_alter_appointment_time_slot'),
    ]

    operations = [
        migrations.AddField(
            model_name='appointment',
            name='full_name',
            field=models.CharField(default='example name', max_length=100),
        ),
        migrations.AddField(
            model_name='appointment',
            name='phone',
            field=models.CharField(default='1234567890', max_length=10),
        ),
    ]
