from django.shortcuts import render, redirect
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from django.contrib import messages
from .models import ClinicSettings
from doctor.decorators import role_required


@method_decorator([never_cache, role_required('doctor')], name='dispatch')
class ClinicSettingsView(LoginRequiredMixin, View):
    login_url = 'doctor:login'

    def get(self, request):
        clinic = ClinicSettings.get()
        working_days = clinic.get_working_days_list()
        all_days = ClinicSettings.WORKING_DAYS_CHOICES
        return render(request, 'clinic/settings.html', {
            'clinic': clinic,
            'working_days': working_days,
            'all_days': all_days,
            'slot_durations': ClinicSettings.SLOT_DURATION_CHOICES,
        })

    def post(self, request):
        clinic = ClinicSettings.get()

        # ── Clinic Info ──────────────────────────
        clinic.clinic_name  = request.POST.get('clinic_name', '').strip()
        clinic.tagline      = request.POST.get('tagline', '').strip()
        clinic.address      = request.POST.get('address', '').strip()
        clinic.city         = request.POST.get('city', '').strip()
        clinic.state        = request.POST.get('state', '').strip()
        clinic.pincode      = request.POST.get('pincode', '').strip()
        clinic.phone        = request.POST.get('phone', '').strip()
        clinic.email        = request.POST.get('email', '').strip()
        clinic.website      = request.POST.get('website', '').strip()

        # ── Logo ─────────────────────────────────
        if 'logo' in request.FILES:
            clinic.logo = request.FILES['logo']

        # ── Doctor Info ──────────────────────────
        clinic.doctor_name      = request.POST.get('doctor_name', '').strip()
        clinic.specialization   = request.POST.get('specialization', '').strip()
        clinic.qualification    = request.POST.get('qualification', '').strip()
        clinic.registration_no  = request.POST.get('registration_no', '').strip()

        # ── Schedule ─────────────────────────────
        clinic.start_time    = request.POST.get('start_time')
        clinic.end_time      = request.POST.get('end_time')
        clinic.slot_duration = int(request.POST.get('slot_duration', 30))
        clinic.lunch_start   = request.POST.get('lunch_start')
        clinic.lunch_end     = request.POST.get('lunch_end')

        # Working days — checkbox se aayenge
        working_days = request.POST.getlist('working_days')
        clinic.working_days = ','.join(working_days)

        # ── Billing ──────────────────────────────
        clinic.default_gst              = request.POST.get('default_gst', 18)
        clinic.default_consultation_fee = request.POST.get('default_consultation_fee', 0)
        clinic.bill_prefix              = request.POST.get('bill_prefix', 'BILL').strip()
        clinic.bill_footer_note         = request.POST.get('bill_footer_note', '').strip()

        clinic.save()
        messages.success(request, 'Clinic settings updated successfully!')
        return redirect('clinic:settings')