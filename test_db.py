import os
import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "doctor_mgmt.settings")
django.setup()

from accounts.models import Patient
p = Patient.objects.filter(phone='1234567892').first()
if p:
    print(f"ID: {p.id}")
    print(f"First Name: '{p.user.first_name}'")
    print(f"Last Name: '{p.user.last_name}'")
    print(f"Get Full Name: '{p.user.get_full_name()}'")
else:
    print("Not found")
