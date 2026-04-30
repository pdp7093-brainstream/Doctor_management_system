from django.contrib.auth.backends import ModelBackend
from accounts.models import Patient

class PhoneBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        try:
            patient = Patient.objects.get(phone=username)
            user = patient.user
            if user.check_password(password):
                return user
            return None
        except Patient.DoesNotExist:
            return None