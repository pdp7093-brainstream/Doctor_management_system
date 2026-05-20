import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'doctor_mgmt.settings')
django.setup()

from appointment.models import Visit
from billing.views import generate_bill_from_visit

visit = Visit.objects.last()
print("Visit:", visit)
bill = generate_bill_from_visit(visit)
print("Bill generated:", bill)
