from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('billing', '0004_alter_bill_visit'),
    ]

    operations = [
        migrations.AddField(
            model_name='bill',
            name='archived_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='bill',
            name='is_archived',
            field=models.BooleanField(default=False),
        ),
    ]
