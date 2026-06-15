from django.shortcuts import render, redirect
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.models import User
from django.db import transaction
from .models import ClinicSettings
from doctor.decorators import role_required, owner_required
from doctor.models import InnerMember


@method_decorator([never_cache, owner_required], name='dispatch')
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
        return redirect('clinic:settings')


# ─────────────────────────────────────────────────────────────────────────────
# FIRST-TIME SETUP WIZARD
# ─────────────────────────────────────────────────────────────────────────────

class SetupClinicView(View):
    """
    Step 1 — Clinic ki basic information leta hai.
    Data session mein save hota hai, Step 2 pe use hoga.
    """

    def _already_setup(self):
        return InnerMember.objects.filter(is_owner=True).exists()

    def get(self, request):
        if self._already_setup():
            return redirect('doctor:login')
        # Session mein pehle se data ho toh pre-fill karo
        prefill = request.session.get('setup_clinic', {})
        return render(request, 'setup/clinic_info.html', {'prefill': prefill})

    def post(self, request):
        if self._already_setup():
            return redirect('doctor:login')

        clinic_name = request.POST.get('clinic_name', '').strip()
        if not clinic_name:
            messages.error(request, 'Clinic ka naam zaroori hai.')
            return render(request, 'setup/clinic_info.html', {'prefill': request.POST})

        # Step 1 ka data session mein rakh do
        request.session['setup_clinic'] = {
            'clinic_name':  clinic_name,
            'tagline':      request.POST.get('tagline', '').strip(),
            'address':      request.POST.get('address', '').strip(),
            'city':         request.POST.get('city', '').strip(),
            'state':        request.POST.get('state', '').strip(),
            'pincode':      request.POST.get('pincode', '').strip(),
            'phone':        request.POST.get('phone', '').strip(),
            'email':        request.POST.get('email', '').strip(),
        }
        return redirect('clinic:setup_owner')


class SetupOwnerView(View):
    """
    Step 2 — Clinic owner ka account banata hai.
    Session se Step 1 ka data nikaal ke ClinicSettings + User + InnerMember
    ek atomic transaction mein create karta hai, phir auto-login karta hai.
    """

    def _already_setup(self):
        return InnerMember.objects.filter(is_owner=True).exists()

    def get(self, request):
        if self._already_setup():
            return redirect('doctor:login')
        # Agar Step 1 skip kiya toh wapas bhejo
        if 'setup_clinic' not in request.session:
            return redirect('clinic:setup_clinic')
        return render(request, 'setup/owner_info.html', {'prefill': {}})

    def post(self, request):
        if self._already_setup():
            return redirect('doctor:login')
        if 'setup_clinic' not in request.session:
            return redirect('clinic:setup_clinic')

        # ── Validate ──────────────────────────────────────────────────────
        first_name   = request.POST.get('first_name', '').strip()
        last_name    = request.POST.get('last_name', '').strip()
        username     = request.POST.get('username', '').strip()
        password     = request.POST.get('password', '')
        password2    = request.POST.get('password2', '')
        doctor_name  = request.POST.get('doctor_name', '').strip()
        specialization = request.POST.get('specialization', '').strip()
        qualification  = request.POST.get('qualification', '').strip()
        registration_no = request.POST.get('registration_no', '').strip()

        errors = {}
        if not first_name:
            errors['first_name'] = 'Pehla naam zaroori hai.'
        if not username:
            errors['username'] = 'Username zaroori hai.'
        elif User.objects.filter(username=username).exists():
            errors['username'] = 'Yeh username pehle se le liya gaya hai.'
        if len(password) < 8:
            errors['password'] = 'Password kam se kam 8 characters ka hona chahiye.'
        elif password != password2:
            errors['password2'] = 'Dono passwords match nahi kar rahe.'

        if errors:
            return render(request, 'setup/owner_info.html', {
                'prefill': request.POST,
                'errors': errors,
            })

        # ── Create everything in one transaction ──────────────────────────
        clinic_data = request.session['setup_clinic']
        try:
            with transaction.atomic():
                # 1. ClinicSettings
                clinic = ClinicSettings.get()
                clinic.clinic_name    = clinic_data['clinic_name']
                clinic.tagline        = clinic_data.get('tagline', '')
                clinic.address        = clinic_data.get('address', '')
                clinic.city           = clinic_data.get('city', '')
                clinic.state          = clinic_data.get('state', '')
                clinic.pincode        = clinic_data.get('pincode', '')
                clinic.phone          = clinic_data.get('phone', '')
                clinic.email          = clinic_data.get('email', '')
                clinic.doctor_name    = doctor_name
                clinic.specialization = specialization
                clinic.qualification  = qualification
                clinic.registration_no = registration_no
                clinic.save()

                # 2. User
                user = User.objects.create_user(
                    username=username,
                    password=password,
                    first_name=first_name,
                    last_name=last_name,
                    email=clinic_data.get('email', ''),
                )

                # 3. InnerMember — owner
                InnerMember.objects.create(
                    user=user,
                    role='doctor',
                    is_owner=True,
                )

        except Exception as e:
            messages.error(request, f'Setup mein koi error aa gayi: {e}')
            return render(request, 'setup/owner_info.html', {'prefill': request.POST, 'errors': {}})

        # ── Cleanup session & auto-login ───────────────────────────────────
        del request.session['setup_clinic']
        login(request, user, backend='django.contrib.auth.backends.ModelBackend')
        messages.success(request, f'Welcome, Dr. {first_name}! Aapka clinic setup ho gaya hai. 🎉')
        return redirect('doctor:dashboard')