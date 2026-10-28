import json
import re
import random
import logging
import calendar
from datetime import date, timedelta
from .models import *
from .forms import *
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, logout as auth_logout, login as auth_login, update_session_auth_hash
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.contrib.auth.forms import SetPasswordForm
from django.conf import settings
from django.utils import timezone
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.utils.http import url_has_allowed_host_and_scheme
from django.urls import reverse
from django.views.decorators.cache import never_cache
from appointment.models import Appointment, LabDocument, PatientUploadedDocument
from doctor.models import InnerMember
from django.core.exceptions import ValidationError
from django.db import OperationalError, ProgrammingError
from django.db.models import Count, Q
from django.core.paginator import Paginator
from django.utils.dateparse import parse_date, parse_time
from appointment.file_validation import validate_uploaded_document
from .emails import send_welcome_email

security_logger = logging.getLogger('accounts.security')

def _patient_dob_bounds():
    today = timezone.localdate()
    min_year = today.year - 120
    min_day = min(today.day, calendar.monthrange(min_year, today.month)[1])
    return date(min_year, today.month, min_day), today - timedelta(days=1)


def _valid_patient_dob(value):
    if not value:
        return True
    try:
        dob = date.fromisoformat(value)
    except (TypeError, ValueError):
        return False
    dob_min, dob_max = _patient_dob_bounds()
    return dob_min <= dob <= dob_max


def activate_patient(request, uidb64, token):
    from .tokens import patient_invite_token_generator
    try:
        user_id = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=user_id)
        patient = user.patient
    except (TypeError, ValueError, OverflowError, User.DoesNotExist, Patient.DoesNotExist):
        user = patient = None

    if not user or user.has_usable_password() or not patient_invite_token_generator.check_token(user, token):
        return render(request, 'authentication/patient_invite_expired.html', status=200)

    form = SetPasswordForm(user, request.POST or None)
    if request.method == 'POST' and form.is_valid():
        form.save()
        auth_login(request, user, backend='django.contrib.auth.backends.ModelBackend')
        security_logger.info('patient_invite_accepted patient_id=%s user_id=%s actor_user_id=%s', patient.pk, user.pk, user.pk)
        messages.success(request, 'Your password has been set. Welcome to Hitshree!')
        return redirect('dashboard')
    return render(request, 'authentication/patient_set_password.html', {'form': form})

def home(request):
    return render(request, 'index.html')

def about(request):
    return render(request, 'about.html')

from .treatments_data import TREATMENT_GROUPS

def treatments(request):
    return render(request, 'treatments.html', {'TREATMENT_GROUPS': TREATMENT_GROUPS})

def terms(request):
    return render(request, 'terms.html')

def feedback(request):
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        email = request.POST.get('email', '').strip()
        phone = request.POST.get('phone', '').strip()
        rating = request.POST.get('rating', '5')
        message = request.POST.get('message', '').strip()

        if not name or not message:
            messages.error(request, 'Name and feedback message are required.')
            return redirect('feedback')

        try:
            rating = int(rating)
            if rating < 1 or rating > 5:
                rating = 5
        except (ValueError, TypeError):
            rating = 5

        from .models import PatientFeedback
        PatientFeedback.objects.create(
            user=request.user if request.user.is_authenticated else None,
            name=name,
            email=email,
            phone=phone,
            rating=rating,
            message=message,
        )
        messages.success(request, 'Thank you for your feedback! We truly appreciate it.')
        return redirect('feedback')

    patient_profile = None
    if request.user.is_authenticated:
        patient_profile = Patient.objects.filter(user=request.user).first()

    return render(request, 'feedback.html', {'patient_profile': patient_profile})

def login(request):
    return render(request, 'authentication/login.html')


# ═════════════════════════════════════════════════════════════
# FAMILY MEMBER OPERATIONS
# ═════════════════════════════════════════════════════════════

@login_required
def add_family_member(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid method'})

    try:
        data = json.loads(request.body)
        name = data.get('name', '').strip()
        relation = data.get('relation', '').strip()
        phone = data.get('phone', '').strip() or None
        gender = data.get('gender', '').strip() or None
        dob = data.get('dob', '').strip() or None
        bld_grop = data.get('bld_grop', '').strip() or None

        if not _valid_patient_dob(dob):
            return JsonResponse({
                'success': False,
                'field': 'dob',
                'error': 'Please enter a valid date of birth',
            })

        if not name or not relation:
            return JsonResponse({'success': False, 'error': 'Name and relation are required.'})

        patient = request.user.patient

        # Duplicate check
        if FamilyMember.objects.filter(
            patient=patient, 
            name__iexact=name, 
            relation__iexact=relation
        ).exists():
            return JsonResponse({'success': False, 'error': f'"{name} ({relation})" already added.'})

        member = FamilyMember.objects.create(
            patient=patient,
            name=name,
            relation=relation,
            phone=phone,
            gender=gender,
            dob=dob,
            bld_grop=bld_grop,
        )

        return JsonResponse({
            'success': True,
            'member': {
                'id': member.id,
                'name': member.name,
                'relation': member.relation,
                'phone': member.phone,
            }
        })

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
def update_family_member(request, hid):
    member_id = hid
    """Update family member via AJAX"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid method'})
    
    # decode possible hashid
    from doctor import hashid as _hashid
    try:
        member_id_val = _hashid.decode_hash(str(member_id))
    except Exception:
        # Fallback for plain digits
        if str(member_id).isdigit():
            member_id_val = int(member_id)
        else:
            return JsonResponse({'success': False, 'error': 'Invalid member id'})

    try:
        member = get_object_or_404(FamilyMember, id=member_id_val, patient=request.user.patient)
        data = json.loads(request.body)
        name = data.get('name', '').strip()
        relation = data.get('relation', '').strip()
        dob = data.get('dob') or None

        if not _valid_patient_dob(dob):
            return JsonResponse({
                'success': False,
                'field': 'dob',
                'error': 'Please enter a valid date of birth',
            })

        if not name or not relation:
            return JsonResponse({'success': False, 'error': 'Name and relation are required.'})

        # Duplicate check (exclude self)
        if FamilyMember.objects.filter(
            patient=request.user.patient,
            name__iexact=name,
            relation__iexact=relation
        ).exclude(id=member_id_val).exists():
            return JsonResponse({'success': False, 'error': f'"{name} ({relation})" already exists.'})

        member.name = name
        member.relation = relation
        member.gender = data.get('gender') or None
        member.dob = dob
        member.bld_grop = data.get('bld_grop') or None
        member.phone = data.get('phone', '').strip() or None
        member.save()

        return JsonResponse({'success': True})

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
def delete_family_member(request, hid):
    member_id = hid
    """Delete family member via AJAX"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid method'})
    
    # decode possible hashid
    from doctor import hashid as _hashid
    try:
        member_id_val = _hashid.decode_hash(str(member_id))
    except Exception:
        # Fallback for plain digits
        if str(member_id).isdigit():
            member_id_val = int(member_id)
        else:
            return JsonResponse({'success': False, 'error': 'Invalid member id'})

    try:
        member = get_object_or_404(FamilyMember, id=member_id_val, patient=request.user.patient)
        member.delete()
        return JsonResponse({'success': True})
    
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


# ═════════════════════════════════════════════════════════════
# AUTHENTICATION VIEWS
# ═════════════════════════════════════════════════════════════

class SignupView(View):
    def get(self, request):
        form = RegistrationForm()
        return render(request, 'authentication/register.html', {'form': form})

    def post(self, request):
        form = RegistrationForm(request.POST)
        if form.is_valid():
            name = form.cleaned_data['name']
            email = form.cleaned_data['email']
            phone = form.cleaned_data['phone']  # Already cleaned/validated
            password = form.cleaned_data['password']

            try:
                #  Create User with EMAIL as username (NOT phone)
                user = User.objects.create_user(
                    username=email,  # ← Username = Email (not phone)
                    password=password,
                    first_name=name,
                    email=email,
                )

                #  Create/Get Patient and store PHONE in patient table
                patient, created = Patient.objects.get_or_create(user=user)
                patient.phone = phone  #  Phone stored here (Patient table)
                patient.save()
                send_welcome_email(request, user, phone=phone, added_by_clinic=False)

                # Auto-login after signup
                user = authenticate(request, username=email, password=password)
                if user is not None:
                    auth_login(request, user)
                    messages.success(request, 'Account created successfully! Welcome.')
                    return redirect('profile')
                else:
                    messages.success(request, 'Account created successfully! Please log in.')
                    return redirect('login')

            except Exception as e:
                form.add_error(None, f'Error creating account: {str(e)}')
                return render(request, 'authentication/register.html', {'form': form})

        return render(request, 'authentication/register.html', {'form': form})


@method_decorator(never_cache, name='dispatch')
class LoginView(View):

    template_name = 'authentication/login.html'

    def get(self, request):
        return render(request, self.template_name)

    def post(self, request):
        email = request.POST.get('email', '').strip().lower()
        password = request.POST.get('password', '')

        if not email or not password:
            return render(request, self.template_name, {
                'error': 'Invalid email or password.',
                'email': email,
            })

        users = list(User.objects.filter(email__iexact=email, patient__isnull=False))
        if not users:
            return render(request, self.template_name, {
                'error': 'Invalid email or password.',
                'email': email,
            })

        user = None
        if len(users) > 1:
            for u in users:
                if u.has_usable_password():
                    user = u
                    break
        else:
            user = users[0]

        if not user or not user.is_active or not user.check_password(password):
            return render(request, self.template_name, {
                'error': 'Invalid email or password.',
                'email': email,
            })

        auth_login(request, user, backend='django.contrib.auth.backends.ModelBackend')

        next_url = request.POST.get('next') or request.GET.get('next')
        if next_url and url_has_allowed_host_and_scheme(
            url=next_url,
            allowed_hosts={request.get_host()},
            require_https=request.is_secure()
        ):
            return redirect(next_url)

        return redirect('profile')

def logout_view(request):
    """Logout user"""
    auth_logout(request)
    messages.success(request, 'You have been logged out.')
    return redirect('login')


# ═════════════════════════════════════════════════════════════
# PROFILE VIEWS
# ═════════════════════════════════════════════════════════════

@never_cache
@login_required(login_url='login')
def dashboard(request):
    """Patient dashboard"""
    patient = Patient.objects.get(user=request.user)
    from therapy.models import PrescriptionTherapy

    my_therapies = PrescriptionTherapy.objects.filter(
        prescription__visit__patient=patient,
    ).exclude(status='cancelled').select_related(
        'therapy', 'prescription__visit__appointment__family_member'
    ).prefetch_related('session_records').order_by('-created_at')
    
    base_appointments = Appointment.objects.filter(
        patient__user=request.user,
        is_archived=False
    ).select_related(
        'patient__user',
        'family_member',
        'doctor__user',
        'booked_by',
    ).prefetch_related('visit_set__prescription')

    search = request.GET.get('search', '').strip()
    date_from = request.GET.get('date_from', '').strip()
    date_to = request.GET.get('date_to', '').strip()
    time_from = request.GET.get('time_from', '').strip()
    time_to = request.GET.get('time_to', '').strip()
    status = request.GET.get('status', '').strip()

    appointments = base_appointments

    if search:
        appointments = appointments.filter(
            Q(patient__user__first_name__icontains=search) |
            Q(patient__user__last_name__icontains=search) |
            Q(patient__user__email__icontains=search) |
            Q(patient__phone__icontains=search) |
            Q(family_member__name__icontains=search) |
            Q(family_member__relation__icontains=search) |
            Q(family_member__phone__icontains=search) |
            Q(doctor__user__first_name__icontains=search) |
            Q(doctor__user__last_name__icontains=search) |
            Q(doctor__user__email__icontains=search) |
            Q(booked_by__first_name__icontains=search) |
            Q(booked_by__last_name__icontains=search) |
            Q(booked_by__email__icontains=search)
        )

    parsed_date_from = parse_date(date_from) if date_from else None
    parsed_date_to = parse_date(date_to) if date_to else None
    parsed_time_from = parse_time(time_from) if time_from else None
    parsed_time_to = parse_time(time_to) if time_to else None

    if parsed_date_from:
        appointments = appointments.filter(appointment_date__gte=parsed_date_from)

    if parsed_date_to:
        appointments = appointments.filter(appointment_date__lte=parsed_date_to)

    if parsed_time_from:
        appointments = appointments.filter(time_slot__gte=parsed_time_from)

    if parsed_time_to:
        appointments = appointments.filter(time_slot__lte=parsed_time_to)

    valid_statuses = [choice[0] for choice in Appointment.status_choices]
    if status in valid_statuses:
        appointments = appointments.filter(status=status)

    appointments = appointments.order_by('-appointment_date', '-time_slot')
    
    appointment_counts = base_appointments.aggregate(
        total_visits=Count('id'),
        pending_appointments=Count('id', filter=Q(status='pending')),
        completed_visits=Count('id', filter=Q(status='completed')),
    )

    # Next upcoming appointment (pending/confirmed; later today or a future date)
    from django.utils import timezone
    today = timezone.localdate()
    now_time = timezone.localtime().time()
    next_appointment = base_appointments.filter(
        status__in=['pending', 'confirmed']
    ).filter(
        Q(appointment_date__gt=today) |
        Q(appointment_date=today, time_slot__gte=now_time)
    ).order_by('appointment_date', 'time_slot').first()

    total_appointments = base_appointments.count()
    paginator = Paginator(appointments, 10)
    page_obj = paginator.get_page(request.GET.get('page'))

    query_params = request.GET.copy()
    query_params.pop('page', None)

    from django.db.models import Sum
    from billing.models import Bill
    total_spent = Bill.objects.filter(visit__patient=patient, payment_status='paid').aggregate(total=Sum('total'))['total'] or 0

    context = {
        'appointments': page_obj,
        'page_obj': page_obj,
        'query_string': query_params.urlencode(),
        'filters': {
            'search': search,
            'date_from': date_from,
            'date_to': date_to,
            'time_from': time_from,
            'time_to': time_to,
            'status': status,
        },
        'status_choices': Appointment.status_choices,
        'total_visits': appointment_counts['total_visits'],
        'total_prescriptions': base_appointments.filter(visit__prescription__isnull=False).values('visit__prescription').distinct().count(),
        'total_appointments': total_appointments,
        'pending_appointments': appointment_counts['pending_appointments'],
        'completed_visits': appointment_counts['completed_visits'],
        'has_any_appointments': appointment_counts['total_visits'] > 0,
        'next_appointment': next_appointment,
        'total_spent': total_spent,
        'my_therapies': my_therapies,
    }
    return render(request, 'pdashboard/dashboard.html', context)


@never_cache
@login_required(login_url='login')
def profile(request):
    """Patient profile page"""
    patient, created = Patient.objects.get_or_create(user=request.user)
    dob_min, dob_max = _patient_dob_bounds()
    profile_dob_error = request.session.pop('profile_dob_error', False)
    profile_dob_value = request.session.pop('profile_dob_value', '')
    family_members = FamilyMember.objects.filter(patient=patient)
    lab_documents = LabDocument.objects.filter(
        visit__patient=patient
    ).select_related(
        'visit__appointment',
        'visit__appointment__family_member',
        'visit__doctor__user',
    )
    try:
        uploaded_documents = list(
            PatientUploadedDocument.objects.filter(
                patient=patient
            ).select_related('family_member', 'uploaded_by')
        )
    except (ProgrammingError, OperationalError):
        uploaded_documents = []

    profile_fields = (
        patient.phone,
        request.user.email,
        patient.dob,
        patient.gender,
        patient.bld_grop,
        patient.address,
    )
    profile_completeness = round(sum(bool(value) for value in profile_fields) * 100 / 6)
    missing_profile_fields = [
        label for value, label in zip(profile_fields, (
            'phone', 'email', 'date of birth', 'gender', 'blood group', 'address'
        )) if not value
    ]
    
    return render(request, 'pdashboard/profile.html', {
        'family_members': family_members,
        'lab_documents': lab_documents,
        'uploaded_documents': uploaded_documents,
        'profile_completeness': profile_completeness,
        'missing_profile_fields': missing_profile_fields,
        'dob_min': dob_min.isoformat(),
        'dob_max': dob_max.isoformat(),
        'profile_dob_error': profile_dob_error,
        'profile_dob_value': profile_dob_value,
    })

@login_required
def upload_profile_document(request):
    if request.method != 'POST':
        return redirect('profile')

    patient, _ = Patient.objects.get_or_create(user=request.user)
    uploaded_file = request.FILES.get('document')
    family_member_id = request.POST.get('family_member_id', '').strip()

    if not uploaded_file:
        messages.error(request, 'Please choose a document to upload.')
        return redirect('profile')
    try:
        original_name = validate_uploaded_document(uploaded_file)
    except ValidationError as exc:
        messages.error(request, '; '.join(exc.messages))
        return redirect('profile')

    family_member = None
    if family_member_id:
        family_member = FamilyMember.objects.filter(
            id=family_member_id,
            patient=patient
        ).first()
        if family_member is None:
            messages.error(request, 'Invalid family member selected.')
            return redirect('profile')

    try:
        PatientUploadedDocument.objects.create(
            patient=patient,
            family_member=family_member,
            file=uploaded_file,
            original_name=original_name,
            uploaded_by=request.user,
        )
    except (ProgrammingError, OperationalError):
        messages.error(request, 'Document upload table is not ready yet. Please run migrations first.')
        return redirect('profile')

    messages.success(request, 'Document uploaded successfully.')
    return redirect('profile')


@login_required
def delete_lab_document(request, hid):
    doc_id = hid
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid method'})
    # decode possible hashid
    from doctor import hashid as _hashid
    try:
        doc_id_val = _hashid.decode_hash(str(doc_id))
    except Exception:
        if str(doc_id).isdigit():
            doc_id_val = int(doc_id)
        else:
            return JsonResponse({'success': False, 'error': 'Invalid document id'}, status=400)

    # find without raising Http404 so we can return JSON
    doc = LabDocument.objects.filter(id=doc_id_val).first()
    if not doc:
        return JsonResponse({'success': False, 'error': 'LabDocument not found'}, status=404)

    is_doctor = hasattr(request.user, 'innermember') and request.user.innermember.role == 'doctor'
    is_patient_owner = (doc.visit.patient.user == request.user)
    is_uploader = (doc.uploaded_by == request.user)

    if not (is_doctor or is_patient_owner or is_uploader):
        return JsonResponse({'success': False, 'error': 'Permission denied'}, status=403)

    try:
        if doc.file:
            doc.file.delete(save=False)
    except Exception:
        pass
    doc.delete()
    return JsonResponse({'success': True})


@login_required
def delete_profile_document(request, hid):
    doc_id = hid
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid method'})
    # decode possible hashid
    from doctor import hashid as _hashid
    try:
        doc_id_val = _hashid.decode_hash(str(doc_id))
    except Exception:
        if str(doc_id).isdigit():
            doc_id_val = int(doc_id)
        else:
            return JsonResponse({'success': False, 'error': 'Invalid document id'}, status=400)

    # find without raising Http404 so we can return JSON
    doc = PatientUploadedDocument.objects.filter(id=doc_id_val).first()
    if not doc:
        return JsonResponse({'success': False, 'error': 'PatientUploadedDocument not found'}, status=404)

    is_doctor = hasattr(request.user, 'innermember') and request.user.innermember.role == 'doctor'
    is_patient_owner = (doc.patient.user == request.user)
    is_uploader = (doc.uploaded_by == request.user)

    if not (is_doctor or is_patient_owner or is_uploader):
        return JsonResponse({'success': False, 'error': 'Permission denied'}, status=403)

    try:
        if doc.file:
            doc.file.delete(save=False)
    except Exception:
        pass
    doc.delete()
    return JsonResponse({'success': True})


@never_cache
@login_required
def profile_settings(request):
    """Update patient profile - Form-based (Traditional POST)"""
    user = request.user
    patient, created = Patient.objects.get_or_create(user=user)

    if request.method != 'POST':
        focus_field = request.GET.get('field', '')
        if focus_field not in {'full_name', 'phone', 'dob', 'gender', 'bld_grop', 'address'}:
            focus_field = ''
        return redirect(f"{reverse('profile')}?edit=1&field={focus_field}")

    full_name = request.POST.get('full_name', request.POST.get('first_name', '')).strip()
    phone = request.POST.get('phone', '').strip()
    address = request.POST.get('address', '').strip() or None
    dob = request.POST.get('dob') or None
    gender = request.POST.get('gender') or None
    bld_grop = request.POST.get('bld_grop') or None

    errors = []
    if not _valid_patient_dob(dob):
        request.session['profile_dob_error'] = True
        request.session['profile_dob_value'] = dob
        return redirect(f"{reverse('profile')}?edit=1&field=dob")

    if not full_name:
        errors.append('Full name is required.')

        # Validate phone if provided
    if phone:
        import re
        cleaned_phone = re.sub(r'[\s\-\+\(\)]', '', phone)
        if not re.match(r'^\d{10,15}$', cleaned_phone):
            errors.append('Invalid phone number format.')
        elif Patient.objects.filter(phone=cleaned_phone).exclude(user=user).exists():
            errors.append('This phone number is already registered!')
        phone = cleaned_phone

    if errors:
        for error in errors:
            messages.error(request, error)
        return redirect(f"{reverse('profile')}?edit=1&field=full_name")

    name_parts = full_name.split(maxsplit=1)
    user.first_name = name_parts[0]
    user.last_name = name_parts[1] if len(name_parts) > 1 else ''
    user.save()

    patient.phone = phone
    patient.address = address
    patient.dob = dob
    patient.gender = gender
    patient.bld_grop = bld_grop

    remove_photo = request.POST.get('remove_photo') == 'true'
    if remove_photo:
        if patient.profile_picture and patient.profile_picture.name != 'profile_pictures/default-avatar.png':
            try:
                patient.profile_picture.delete(save=False)
            except Exception:
                pass
        patient.profile_picture = 'profile_pictures/default-avatar.png'
    elif 'profile_picture' in request.FILES:
        patient.profile_picture = request.FILES['profile_picture']

    patient.save()
    messages.success(request, 'Profile updated successfully.')
    return redirect('profile')

@login_required
def remove_profile_picture(request):
    if request.method == 'POST':
        patient, _ = Patient.objects.get_or_create(user=request.user)
        if patient.profile_picture and patient.profile_picture.name != 'profile_pictures/default-avatar.png':
            try:
                patient.profile_picture.delete(save=False)
            except Exception:
                pass
        patient.profile_picture = 'profile_pictures/default-avatar.png'
        patient.save()
        return JsonResponse({'success': True})
    return JsonResponse({'success': False, 'error': 'Invalid request method'})

class ChangePasswordView(LoginRequiredMixin, View):
    """Change password view"""
    login_url = 'login'

    def get(self, request):
        form = ChangePasswordForm()
        return render(request, 'authentication/change_password.html', {'form': form})

    def post(self, request):
        form = ChangePasswordForm(request.POST)     
        if form.is_valid():
            user = request.user
            old_password = form.cleaned_data['old_password']
            new_password = form.cleaned_data['new_password']

            # Check if old password is correct
            if user.check_password(old_password):
                user.set_password(new_password)
                user.save()
                # Maintain session after password change
                update_session_auth_hash(request, user)
                return redirect('login')
            else:
                messages.error(request, 'The old password you entered is incorrect.')

        return render(request, 'authentication/change_password.html', {'form': form})

# CHANGEING THE PHONE NUMBER
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
import json

@login_required
def change_phone(request):
    if request.method == 'POST' and request.headers.get('x-requested-with') == 'XMLHttpRequest':
        try:
            # Check authentication
            if not request.user.is_authenticated or not hasattr(request.user, 'patient'):
                return JsonResponse({'success': False, 'error': 'User not authenticated'}, status=401)
            
            data = json.loads(request.body or '{}')
            new_phone = data.get('phone', '').strip()
            otp = data.get('otp', '').strip()
            
            # Validate phone number
            if not new_phone:
                return JsonResponse({'success': False, 'error': 'Phone number is required'}, status=400)
            
            if not otp:
                return JsonResponse({'success': False, 'error': 'OTP is required'}, status=400)
            
            # Phone format validation - exactly 10 digits
            if not re.match(r'^\d{10}$', new_phone):
                return JsonResponse({'success': False, 'error': 'Phone number must contain exactly 10 digits'}, status=400)
            
            # Check if phone is same as current
            if new_phone == request.user.patient.phone:
                return JsonResponse({'success': False, 'error': 'New phone number must be different from current number'}, status=400)
            
            # Check for duplicate phone in database
            from .models import Patient
            if Patient.objects.filter(phone=new_phone).exclude(user=request.user).exists():
                return JsonResponse({'success': False, 'error': 'This phone number is already registered with another account'}, status=400)
            
            # Update phone number
            request.user.patient.phone = new_phone
            request.user.patient.save()
            
            return JsonResponse({
                'success': True, 
                'message': 'Phone number updated successfully',
                'phone': new_phone
            }, status=200)
            
        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'error': 'Invalid request format'}, status=400)
        except Exception as e:
            import traceback
            traceback.print_exc()
            return JsonResponse({'success': False, 'error': f'An error occurred: {str(e)}'}, status=400)
    
    return JsonResponse({'success': False, 'error': 'Invalid request method'}, status=405)
