import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('medicine', '0006_remove_purchaseitem_cost_strip_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='MedicineType',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=50, unique=True)),
                ('is_active', models.BooleanField(default=True)),
                ('sort_order', models.PositiveIntegerField(default=0)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'ordering': ['sort_order', 'name'],
            },
        ),
        migrations.AddField(
            model_name='medicine',
            name='medicine_type_new',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='medicines',
                to='medicine.medicinetype',
            ),
        ),
    ]
