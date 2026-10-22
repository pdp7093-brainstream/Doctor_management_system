from django.db import migrations

OLD_DISPLAY_MAP = {
    'tablet': 'Tablet',
    'syrup': 'Syrup',
    'injection': 'Injection',
    'capsule': 'Capsule',
    'drops': 'Drops',
    'cream': 'Cream',
}

SEED_TYPES = [
    'Tablet',
    'Syrup',
    'Injection',
    'Capsule',
    'Drops',
    'Cream',
    'Powder',
    'Dry Kadha',
    'Liquid Kadha',
    'Churna',
    'Vati / Gutika',
    'Kwath / Kashayam',
    'Asava / Arishta',
    'Ghrita',
    'Taila (Oil)',
    'Bhasma',
    'Avaleha',
    'Guggulu',
    'Arka',
    'Lepa',
]


def migrate_forward(apps, schema_editor):
    MedicineType = apps.get_model('medicine', 'MedicineType')
    Medicine = apps.get_model('medicine', 'Medicine')

    # Seed all default types
    created_map = {}
    for idx, name in enumerate(SEED_TYPES):
        obj, _ = MedicineType.objects.get_or_create(
            name=name,
            defaults={'sort_order': idx, 'is_active': True}
        )
        created_map[name.lower()] = obj

    # Ensure every distinct old medicine_type value has a MedicineType row
    distinct_types = Medicine.objects.values_list('medicine_type', flat=True).distinct()
    for raw_type in distinct_types:
        if not raw_type:
            continue
        display_name = OLD_DISPLAY_MAP.get(str(raw_type).strip().lower(), str(raw_type).strip().title())
        if display_name.lower() not in created_map:
            obj, _ = MedicineType.objects.get_or_create(
                name=display_name,
                defaults={'sort_order': len(created_map), 'is_active': True}
            )
            created_map[display_name.lower()] = obj

    # Set each Medicine's medicine_type_new from its old value
    for med in Medicine.objects.all():
        if med.medicine_type:
            display_name = OLD_DISPLAY_MAP.get(str(med.medicine_type).strip().lower(), str(med.medicine_type).strip().title())
            type_obj = MedicineType.objects.filter(name__iexact=display_name).first()
            if type_obj:
                med.medicine_type_new = type_obj
                med.save(update_fields=['medicine_type_new'])


def migrate_reverse(apps, schema_editor):
    Medicine = apps.get_model('medicine', 'Medicine')
    REVERSE_MAP = {
        'tablet': 'tablet',
        'syrup': 'syrup',
        'injection': 'injection',
        'capsule': 'capsule',
        'drops': 'drops',
        'cream': 'cream',
    }
    for med in Medicine.objects.all():
        if med.medicine_type_new:
            name_lower = med.medicine_type_new.name.lower()
            med.medicine_type = REVERSE_MAP.get(name_lower, name_lower[:20])
            med.save(update_fields=['medicine_type'])


class Migration(migrations.Migration):

    dependencies = [
        ('medicine', '0007_medicinetype_medicine_medicine_type_new'),
    ]

    operations = [
        migrations.RunPython(migrate_forward, migrate_reverse),
    ]
