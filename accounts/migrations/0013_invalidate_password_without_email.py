from django.contrib.auth.hashers import make_password
from django.db import migrations


def invalidate_passwords_without_email(apps, schema_editor):
    Patient = apps.get_model('accounts', 'Patient')
    User = apps.get_model('auth', 'User')
    user_ids = Patient.objects.values_list('user_id', flat=True)
    qs = User.objects.filter(id__in=user_ids).filter(email__in=['', None]) \
        .exclude(password='').exclude(password__startswith='!')
    count = 0
    for user in qs:
        user.password = make_password(None)
        user.save(update_fields=['password'])
        count += 1
    print(f'Invalidated {count} patient passwords without email')


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0012_clear_none_patient_phones'),
    ]

    operations = [
        migrations.RunPython(invalidate_passwords_without_email, migrations.RunPython.noop),
    ]