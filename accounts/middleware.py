from django.contrib import messages
from django.shortcuts import redirect
from django.urls import Resolver404, resolve
from django.contrib.auth import get_user_model

from accounts.models import Patient
from doctor.models import InnerMember


class RoleRedirectMiddleware:
    AUTH_URLS = {('', 'login'), ('', 'signup'), ('doctor', 'login'), ('doctor', 'register')}
    STAFF_NAMESPACES = {'doctor', 'medicine', 'billing', 'expenses', 'reports_archive', 'clinic'}
    PATIENT_APPOINTMENT_URLS = {
        'appointment',
        'get_slots',
        'appointment_detail',
        'print_prescription',
    }
    PATIENT_ONLY_URLS = {
        'dashboard', 'profile', 'profile-setting', 'add_family_member',
        'update_family_member', 'delete_family_member',
    }
    SKIPPED_NAMES = {
        'logout', 'activate_patient', 'password_reset', 'password_reset_done',
        'password_reset_confirm', 'password_reset_complete',
    }

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.method not in {'GET', 'HEAD'}:
            return self.get_response(request)

        path = request.path_info.lstrip('/')
        if path.startswith(('static/', 'media/', 'admin/')):
            return self.get_response(request)
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return self.get_response(request)
        if 'application/json' in request.headers.get('Accept', ''):
            return self.get_response(request)

        try:
            match = resolve(request.path_info)
        except Resolver404:
            return self.get_response(request)

        namespace = match.namespace
        top_level_namespace = match.namespaces[0] if match.namespaces else ''
        name = match.url_name
        if name in self.SKIPPED_NAMES or (namespace == 'doctor' and name == 'logout'):
            return self.get_response(request)

        if not request.user.is_authenticated:
            return self.get_response(request)

        patient = getattr(request, '_role_redirect_patient', None)
        member = getattr(request, '_role_redirect_member', None)
        if not hasattr(request, '_role_redirect_detected'):
            user = get_user_model().objects.select_related('patient', 'innermember').get(pk=request.user.pk)
            try:
                patient = user.patient
            except Patient.DoesNotExist:
                patient = None
            try:
                member = user.innermember
            except InnerMember.DoesNotExist:
                member = None
            request._role_redirect_patient = patient
            request._role_redirect_member = member
            request._role_redirect_detected = True

        auth_url = (namespace, name) in self.AUTH_URLS
        if auth_url:
            if member:
                return redirect('billing:bill_list' if member.role == 'biller' else 'doctor:dashboard')
            if patient:
                return redirect('dashboard')

        if patient and not member:
            staff_panel = top_level_namespace in self.STAFF_NAMESPACES or (
                namespace == 'appointment' and name not in self.PATIENT_APPOINTMENT_URLS
            )
            if staff_panel:
                messages.info(request, 'That page is only for clinic staff.')
                return redirect('dashboard')

        if member and namespace == '' and name in self.PATIENT_ONLY_URLS:
            return redirect('billing:bill_list' if member.role == 'biller' else 'doctor:dashboard')

        return self.get_response(request)
