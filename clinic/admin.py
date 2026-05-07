from django.contrib import admin
from .models import ClinicSettings


@admin.register(ClinicSettings)
class ClinicSettingsAdmin(admin.ModelAdmin):
    fieldsets = (
        ('Clinic Info', {
            'fields': (
                'clinic_name', 'tagline', 'logo',
                'address', 'city', 'state', 'pincode',
                'phone', 'email', 'website',
            )
        }),
        ('Doctor Info', {
            'fields': (
                'doctor_name', 'specialization',
                'qualification', 'registration_no',
            )
        }),
        ('Schedule Settings', {
            'fields': (
                'start_time', 'end_time',
                'slot_duration', 'lunch_start',
                'lunch_end', 'working_days',
            )
        }),
        ('Billing Settings', {
            'fields': (
                'default_gst', 'default_consultation_fee',
                'bill_prefix', 'bill_footer_note',
            )
        }),
    )

    def has_add_permission(self, request):
        # Sirf ek record allow karo
        return not ClinicSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False