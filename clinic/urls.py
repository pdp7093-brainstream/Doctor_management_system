from django.urls import path
from .views import ClinicSettingsView, SetupClinicView, SetupOwnerView

app_name = 'clinic'

urlpatterns = [
    path('settings/', ClinicSettingsView.as_view(), name='settings'),
    path('setup/clinic-info/', SetupClinicView.as_view(), name='setup_clinic'),
    path('setup/owner-info/', SetupOwnerView.as_view(), name='setup_owner'),
]