from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('appointment', '0008_labdocument'),
    ]

    operations = [
        migrations.AddField(
            model_name='appointment',
            name='cancellation_reason',
            field=models.TextField(blank=True, null=True),
        ),
    ]
