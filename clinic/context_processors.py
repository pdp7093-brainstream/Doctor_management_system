from .models import ClinicSettings 


def clinic_settings(request):
    return {'clinic':ClinicSettings.get()}