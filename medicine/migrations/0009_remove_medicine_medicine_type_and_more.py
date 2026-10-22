from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('medicine', '0008_migrate_medicine_types'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='medicine',
            name='medicine_type',
        ),
        migrations.RenameField(
            model_name='medicine',
            old_name='medicine_type_new',
            new_name='medicine_type',
        ),
    ]
