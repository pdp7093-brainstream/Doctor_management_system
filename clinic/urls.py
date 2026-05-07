from django.urls import path
from .views import ClinicSettingsView

app_name = 'clinic'

urlpatterns = [
    path('settings/', ClinicSettingsView.as_view(), name='settings'),
]