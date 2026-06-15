from django.db import migrations

def assign_owner(apps, schema_editor):
    InnerMember = apps.get_model('doctor', 'InnerMember')
    ClinicSettings = apps.get_model('clinic', 'ClinicSettings')
    
    # Check if this is an existing database (clinic settings exist)
    if ClinicSettings.objects.exists():
        # Check if any owner exists
        if not InnerMember.objects.filter(is_owner=True).exists():
            # Find the first doctor and make them the owner
            first_doctor = InnerMember.objects.filter(role='doctor').first()
            if first_doctor:
                first_doctor.is_owner = True
                first_doctor.save(update_fields=['is_owner'])

def reverse_assign_owner(apps, schema_editor):
    pass  # No need to revert since is_owner default is False anyway

class Migration(migrations.Migration):

    dependencies = [
        ('doctor', '0011_add_is_owner_to_innermember'),
        ('clinic', '0003_clinicsettings_phone_consultation_fee_and_more'),
    ]

    operations = [
        migrations.RunPython(assign_owner, reverse_assign_owner),
    ]
