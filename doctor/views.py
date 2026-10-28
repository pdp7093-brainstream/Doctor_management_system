import json
import logging
import random
import re
from datetime import date, timedelta

from django.shortcuts import render, redirect, get_object_or_404
from django.db import OperationalError, ProgrammingError, transaction
from django.contrib.auth import authenticate, login, logout as auth_logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.conf import settings
from django.views.decorators.cache import never_cache
from django.views import View
from .decorators import role_required, owner_required
from .models import InnerMember
from .utils import get_default_doctor
from appointment.models import Appointment, LabDocument, PatientUploadedDocument, PatientOldDocument
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views.decorators.http import require_POST
from django.http import JsonResponse
from accounts.models import Patient
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db.models import Avg, Count, Q
from django.core.paginator import Paginator
from accounts.models import FamilyMember
from accounts.emails import send_welcome_email
from appointment.file_validation import validate_uploaded_document

logger = logging.getLogger(__name__)

def login_view(request):
    patient_logged_in = request.user.is_authenticated and Patient.objects.filter(user=request.user).exists()
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        
        # Pre-check for pending approval
        try:
            pending_user = User.objects.get(username=username)
            if not pending_user.is_active and InnerMember.objects.filter(user=pending_user).exists():
                return render(request, 'doctor/login.html', {'error': 'Your account is pending approval by the clinic owner.'})
        except User.DoesNotExist:
            pass

        user = authenticate(request, username=username, password=password)

        if user is not None:
            try:
                member = InnerMember.objects.get(user=user)
                role = member.role
            except InnerMember.DoesNotExist:
                return render(request, 'doctor/login.html', {'error': 'Role not assigned'})
            
            login(request, user)

            if role == 'doctor':
                return redirect('doctor:dashboard')
            else:
                return redirect('billing:bill_list')
        else:
            return render(request, 'doctor/login.html', {'error': 'Invalid credentials'})

    return render(request, 'doctor/login.html', {'patient_logged_in': patient_logged_in})

@never_cache
def forgot_password(request):
    username = request.POST.get('username', '').strip() if request.method == 'POST' else ''
    error = None
    success = None
    show_otp_form = False

    if request.method == 'POST':
        otp = request.POST.get('otp', '').strip()
        new_password = request.POST.get('new_password', '')
        confirm_password = request.POST.get('confirm_password', '')

        if otp or new_password or confirm_password:
            # OTP validation + password reset stage
            session_otp = request.session.get('doctor_reset_otp')
            user_id = request.session.get('doctor_reset_user_id')

            if not username:
                error = 'Username is required.'
                show_otp_form = True
            elif not session_otp or not user_id:
                error = 'OTP session expired. Request a new OTP.'
            elif not otp:
                error = 'OTP is required.'
                show_otp_form = True
            elif otp != str(session_otp):
                error = 'Invalid OTP. Please try again.'
                show_otp_form = True
            elif not new_password or not confirm_password:
                error = 'New password and confirm password are required.'
                show_otp_form = True
            elif new_password != confirm_password:
                error = 'Passwords do not match.'
                show_otp_form = True
            else:
                if len(new_password) < 8:
                    error = 'Password must be at least 8 characters long.'
                    show_otp_form = True
                elif not re.search(r'[A-Z]', new_password):
                    error = 'Password must contain at least one uppercase letter.'
                    show_otp_form = True
                elif not re.search(r'[a-z]', new_password):
                    error = 'Password must contain at least one lowercase letter.'
                    show_otp_form = True
                elif not re.search(r'[0-9]', new_password):
                    error = 'Password must contain at least one number.'
                    show_otp_form = True
                elif not re.search(r'[!@#$%^&*(),.?":{}|<>]', new_password):
                    error = 'Password must contain at least one special character.'
                    show_otp_form = True
                else:
                    try:
                        user = User.objects.get(id=user_id)
                        user.set_password(new_password)
                        user.save()
                        request.session.pop('doctor_reset_otp', None)
                        request.session.pop('doctor_reset_user_id', None)
                        success = 'Password reset successful. Please login with your new password.'
                    except User.DoesNotExist:
                        error = 'Account no longer exists.'
        else:
            # Request OTP stage
            if not username:
                error = 'Username is required.'
            else:
                try:
                    user = User.objects.get(username=username)
                    InnerMember.objects.get(user=user)

                    if not user.email:
                        error = 'User does not have an email address. Contact admin.'
                    else:
                        otp = str(random.randint(100000, 999999))
                        request.session['doctor_reset_otp'] = otp
                        request.session['doctor_reset_user_id'] = user.id
                        show_otp_form = True

                        send_mail(
                            subject='Clinic Password Reset OTP',
                            message=f'Your password reset OTP is {otp}. Use this to reset your password.',
                            from_email=settings.DEFAULT_FROM_EMAIL,
                            recipient_list=[user.email],
                            fail_silently=False,
                        )

                        success = 'OTP has been sent to your registered email address. Check your inbox.'

                except User.DoesNotExist:
                    error = 'Invalid username.'
                except InnerMember.DoesNotExist:
                    error = 'Account is not a clinic doctor/staff.'
                except Exception as exc:
                    logger.exception('forgot_password email send failed: %s', exc)
                    error = 'Unable to send OTP email. Please try again later.'

    return render(request, 'doctor/forgot_password.html', {
        'error': error,
        'success': success,
        'show_otp_form': show_otp_form,
        'username': username,
    })

# Logout 
def logout_view(request):
    auth_logout(request)
    messages.success(request, 'You have been logged out.')
    return redirect('doctor:login')

@method_decorator([never_cache, role_required("doctor")], name="dispatch")
class DashboardView(View):
    def get(self, request):
        today  = timezone.localdate()
        default_doctor = get_default_doctor()

        today_appointments = Appointment.objects.filter(
            appointment_date=today,
            is_archived=False,
            doctor=default_doctor,
        ).select_related('patient__user', 'family_member', 'doctor__user', 'booked_by').order_by('time_slot') if default_doctor else Appointment.objects.none()

        today_counts = Appointment.objects.filter(
            appointment_date=today,
            is_archived=False,
            doctor=default_doctor,
        ).aggregate(
            total=Count('id'),
            remaining_today=Count('id', filter=Q(status='pending')),
        ) if default_doctor else {'total': 0, 'remaining_today': 0}
        total_staff = InnerMember.objects.filter(role='biller').count()

        context = {
            'today_appointments'  : today_appointments,
            'total'               : today_counts['total'],
            'remaining_today'     : today_counts['remaining_today'],
            'total_staff'         : total_staff,
        }
        return render(request, 'doctor/dashboard.html', context)

@never_cache
@login_required
@require_POST
def cancel_appointment(request, hid):
    try:
        payload = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        payload = {}

    reason = (payload.get('cancellation_reason') or "").strip()
    if not reason:
        return JsonResponse({'success': False, 'error': 'Cancellation reason is required.'}, status=400)

    try:
        from doctor import hashid as _hashid
        appointment_id = _hashid.decode_hash(str(hid))
    except Exception:
        # Fallback to plain id if it's purely digits and decoding failed, or return error
        if isinstance(hid, str) and hid.isdigit():
            appointment_id = int(hid)
        else:
            return JsonResponse({'success': False, 'error': 'Invalid appointment ID.'}, status=400)

    doctor = InnerMember.objects.get(user=request.user)
    appointment = get_object_or_404(
        Appointment.objects.select_related('doctor'),
        id=appointment_id,
        is_archived=False
    )

    if appointment.status == 'cancelled':
        return JsonResponse({'success': False, 'error': 'Appointment is already cancelled.'}, status=400)

    if appointment.status == 'completed':
        return JsonResponse({'success': False, 'error': 'Completed appointments cannot be cancelled.'}, status=400)

    if appointment.doctor is not None and appointment.doctor != doctor:
        return JsonResponse({'success': False, 'error': 'You do not have permission to cancel this appointment.'}, status=403)

    appointment.status = 'cancelled'
    appointment.cancellation_reason = reason
    appointment.save(update_fields=['status', 'cancellation_reason'])

    today = timezone.localdate()
    default_doctor = get_default_doctor()
    today_counts = Appointment.objects.filter(
        appointment_date=today,
        is_archived=False,
        doctor=default_doctor,
    ).aggregate(
        total=Count('id'),
        remaining_today=Count('id', filter=Q(status='pending')),
    ) if default_doctor else {'total': 0, 'remaining_today': 0}
    
    return JsonResponse({
        'success': True,
        'status': appointment.get_status_display(),
        'status_raw': appointment.status,
        'total': today_counts['total'],
        'remaining_today': today_counts['remaining_today'],
    })


@never_cache
@login_required
def billing(request):
     return render(request, 'doctor/billing.html')

@never_cache
@role_required('doctor')
def manage_patients(request):
    search = request.GET.get('search', '').strip()

    # Exclude patients whose user account belongs to any staff (doctor, biller, etc.)
    patients = Patient.objects.select_related('user').exclude(user__innermember__isnull=False)
    family_members = FamilyMember.objects.select_related('patient__user').exclude(patient__user__innermember__isnull=False)

    combined = []

    # Main Patients
    for p in patients:
        combined.append({
            'id': p.id,
            'name': f"{p.user.first_name} {p.user.last_name}",
            'phone': p.phone,
            'gender': p.gender,
            'type': 'main',
            'email': p.user.email,
            'login_status': p.login_status,
            'invite_sent_at': p.invite_sent_at,
        })

    # Family Members (as patients)
    for f in family_members:
        combined.append({
            'id': f.id,
            'name': f.name,
            'phone': f.phone,
            'gender': f.gender,
            'type': 'family'
        })

    # Sorting (important UX)
    combined = sorted(combined, key=lambda x: x['name'].lower())

    if search:
        search_lower = search.lower()
        combined = [
            patient for patient in combined
            if search_lower in patient['name'].lower()
            or search_lower in (patient.get('phone') or '').lower()
        ]

    paginator = Paginator(combined, 10)
    page_obj = paginator.get_page(request.GET.get('page'))

    return render(request, 'doctor/manage_patients.html', {
        'patients': page_obj,
        'page_obj': page_obj,
        'search': search,
    }) 


@never_cache
@role_required('doctor')
def view_patient_dynamic(request, type, hid):

    # decode hashed id into integer id
    from . import hashid as _hashid
    try:
        id = _hashid.decode_hash(hid)
    except Exception:
        # invalid hash → 404
        return get_object_or_404(Patient, id=0)  # will raise 404

    if type == 'main':
        patient = get_object_or_404(Patient, id=id)
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

        # paginate documents (5 per page)
        lab_paginator = Paginator(lab_documents, 5)
        lab_page = lab_paginator.get_page(request.GET.get('lab_page'))

        upload_paginator = Paginator(uploaded_documents, 5)
        upload_page = upload_paginator.get_page(request.GET.get('upload_page'))

        # fetch appointments for the main patient
        appointments = Appointment.objects.filter(patient=patient, family_member__isnull=True).order_by('-appointment_date', '-time_slot')
        appt_paginator = Paginator(appointments, 5)
        appt_page = appt_paginator.get_page(request.GET.get('appt_page'))

        old_documents = PatientOldDocument.objects.filter(patient=patient, family_member__isnull=True)
        old_doc_paginator = Paginator(old_documents, 5)
        old_doc_page = old_doc_paginator.get_page(request.GET.get('old_doc_page'))

        return render(request, 'doctor/view_patient.html', {
            'patient': patient,
            'family_members': family_members,
            'is_family': False,
            'lab_page_obj': lab_page,
            'uploaded_page_obj': upload_page,
            'appt_page_obj': appt_page,
            'old_doc_page_obj': old_doc_page,
        })

    else:
        member = get_object_or_404(FamilyMember, id=id)
        lab_documents = LabDocument.objects.filter(
            visit__patient=member.patient
        ).select_related(
            'visit__appointment',
            'visit__appointment__family_member',
            'visit__doctor__user',
        )
        try:
            uploaded_documents = list(
                PatientUploadedDocument.objects.filter(
                    patient=member.patient
                ).select_related('family_member', 'uploaded_by')
            )
        except (ProgrammingError, OperationalError):
            uploaded_documents = []

        # paginate documents (5 per page)
        lab_paginator = Paginator(lab_documents, 5)
        lab_page = lab_paginator.get_page(request.GET.get('lab_page'))

        upload_paginator = Paginator(uploaded_documents, 5)
        upload_page = upload_paginator.get_page(request.GET.get('upload_page'))

        # fetch appointments for the family member
        appointments = Appointment.objects.filter(family_member=member).order_by('-appointment_date', '-time_slot')
        appt_paginator = Paginator(appointments, 5)
        appt_page = appt_paginator.get_page(request.GET.get('appt_page'))

        old_documents = PatientOldDocument.objects.filter(family_member=member)
        old_doc_paginator = Paginator(old_documents, 5)
        old_doc_page = old_doc_paginator.get_page(request.GET.get('old_doc_page'))

        return render(request, 'doctor/view_patient.html', {
            'member': member,
            'parent': member.patient,
            'family_members': member.patient.members.all(),
            'is_family': True,
            'lab_page_obj': lab_page,
            'uploaded_page_obj': upload_page,
            'appt_page_obj': appt_page,
            'old_doc_page_obj': old_doc_page,
        })
    
@never_cache
@role_required('doctor')
@require_POST
def send_patient_invite(request, hid):
    from . import hashid as _hashid
    from accounts.services.invites import send_patient_invite_email

    try:
        patient_id = _hashid.decode_hash(hid)
    except Exception:
        return get_object_or_404(Patient, id=0)
    patient = get_object_or_404(Patient.objects.select_related('user'), pk=patient_id)
    return_to = request.POST.get('next', '')
    if not url_has_allowed_host_and_scheme(return_to, {request.get_host()}, require_https=request.is_secure()):
        return_to = reverse('doctor:manage_patients')

    status, email = send_patient_invite_email(patient, request, request.user)
    if status == 'sent':
        messages.success(request, f'Login invite sent to {email}.')
    elif status == 'recent':
        messages.error(request, 'Please wait 2 minutes before sending another invite.')
    elif status == 'no_email':
        messages.error(request, 'Add an email address before sending a login invite.')
    elif status == 'active':
        messages.error(request, 'This patient already has an active login.')
    elif status == 'invalid_email':
        messages.error(request, 'Enter a valid email address before sending a login invite.')
    else:
        messages.error(request, 'The login invite could not be sent. Please try again.')
    return redirect(return_to)


@never_cache
@role_required('doctor')
def edit_patient(request, hid):
    from . import hashid as _hashid
    from accounts.services.invites import send_patient_invite_email
    try:
        patient_id = _hashid.decode_hash(hid)
    except Exception:
        return get_object_or_404(Patient, id=0)

    patient = get_object_or_404(Patient, pk=patient_id)

    if request.method == 'POST':

        name      = request.POST.get('name', '').strip()
        email     = request.POST.get('email', '').strip().lower()
        active_login = patient.login_status == 'active'
        if active_login:
            email = patient.user.email
        dob       = request.POST.get('dob')
        gender    = request.POST.get('gender')
        phone     = request.POST.get('phone', '').strip()
        bld_grop  = request.POST.get('bld_grop')
        address   = request.POST.get('address')

        # EMAIL DUPLICATE CHECK
        if not active_login and email and User.objects.filter(
            Q(email__iexact=email) | Q(username__iexact=email)
        ).exclude(pk=patient.user.pk).exists():
            messages.error(request, 'Email already in use.')
            return render(request, 'doctor/edit_patient.html', {
                'patient': patient
            })

        #  PHONE DUPLICATE CHECK
        if phone and Patient.objects.filter(phone=phone).exclude(pk=patient.pk).exists():

            return render(request, 'doctor/edit_patient.html', {
                'patient': patient
            })

        #  UPDATE USER
        if name:
            name_parts = name.split(' ', 1)
            patient.user.first_name = name_parts[0]
            patient.user.last_name = name_parts[1] if len(name_parts) > 1 else ''
        if not active_login:
            patient.user.email      = email or patient.user.email
            patient.user.username   = email or patient.user.username
        patient.user.save()

        # UPDATE PATIENT
        patient.phone     = phone
        patient.address   = address
        patient.dob       = dob if dob else None
        patient.gender    = gender
        patient.bld_grop  = bld_grop
        patient.save()

        if request.POST.get('send_login_invite') == 'on' and not active_login:
            if not patient.user.email:
                messages.warning(request, 'Add an email to send a login invite')
            else:
                invite_status, invite_email = send_patient_invite_email(patient, request, request.user)
                if invite_status == 'sent':
                    messages.success(request, f'Patient updated and login invite sent to {invite_email}')
                elif invite_status == 'recent':
                    messages.warning(request, 'Patient updated. Invite was sent recently, try again in a minute.')
                elif invite_status == 'no_email':
                    messages.warning(request, 'Add an email to send a login invite')
                elif invite_status == 'invalid_email':
                    messages.error(request, 'Patient updated, but the email address is invalid and the invite was not sent.')
                elif invite_status == 'error':
                    messages.error(request, 'Patient updated, but the login invite could not be sent. Please try again.')

        return redirect('doctor:manage_patients')

    return render(request, 'doctor/edit_patient.html', {
        'patient': patient
    })

@never_cache
@role_required('doctor')
def delete_patient(request, hid):
    from . import hashid as _hashid
    try:
        patient_id = _hashid.decode_hash(hid)
    except Exception:
        return get_object_or_404(Patient, id=0)

    patient = get_object_or_404(Patient, pk=patient_id)

    if request.method == 'POST':
        patient.user.delete()

    return redirect('doctor:manage_patients')

# doctor/views.py - replaced add_patient view

@never_cache
@role_required('doctor')
def add_patient(request):
    all_patients = Patient.objects.all().select_related('user').order_by('user__first_name')

    if request.method == 'POST':
        name      = request.POST.get('name', '').strip()
        email     = request.POST.get('email', '').strip().lower()
        dob       = request.POST.get('dob')
        gender    = request.POST.get('gender')
        phone     = request.POST.get('phone', '').strip()
        bld_grop  = request.POST.get('bld_grop')
        address   = request.POST.get('address')
        parent_id = request.POST.get('parent_patient')
        relation  = request.POST.get('relation', '').strip()

        if not name:

            return render(request, 'doctor/add_patient.html', {'patients': all_patients})

        # ── Case 1: Parent selected → create only FamilyMember ──────────
        if parent_id and relation:
            try:
                parent_patient = Patient.objects.get(id=parent_id)

                # Duplicate check
                if FamilyMember.objects.filter(
                    patient=parent_patient,
                    name__iexact=name,
                    relation__iexact=relation
                ).exists():
                    return render(request, 'doctor/add_patient.html', {'patients': all_patients})

                FamilyMember.objects.create(
                    patient  = parent_patient,
                    name     = name,
                    relation = relation,
                    phone    = phone,          # optional — parent ka nahi, jo dala woh
                    gender   = gender or None,
                    dob      = dob or None,
                    bld_grop = bld_grop or None,
                )

                return redirect('doctor:manage_patients')

            except Patient.DoesNotExist:
               
                return render(request, 'doctor/add_patient.html', {'patients': all_patients})

        # ── Case 2: No parent → Create Main Patient (User + Patient) ────
        if not email:
            messages.error(request, 'Email is required.')
            return render(request, 'doctor/add_patient.html', {'patients': all_patients})

        try:
            validate_email(email)
        except ValidationError:
            messages.error(request, 'Enter a valid email address.')
            return render(request, 'doctor/add_patient.html', {'patients': all_patients})

        if User.objects.filter(Q(email__iexact=email) | Q(username__iexact=email)).exists():
            messages.error(request, 'Email already in use.')
            return render(request, 'doctor/add_patient.html', {'patients': all_patients})

        name_parts = name.split(' ', 1)
        first_name = name_parts[0]
        last_name  = name_parts[1] if len(name_parts) > 1 else ''

        try:
            with transaction.atomic():
                user = User.objects.create_user(
                    username   = email,
                    email      = email,
                    first_name = first_name,
                    last_name  = last_name,
                )
                user.set_unusable_password()
                user.save()
                # The Patient object is auto-created via a post_save signal on the User model.
                # So we fetch it and update it, rather than creating a duplicate.
                patient = user.patient
                patient.phone    = phone or None
                patient.address  = address
                patient.dob      = dob or None
                patient.gender   = gender or None
                patient.bld_grop = bld_grop or None
                patient.save()

            send_welcome_email(request, user, phone=phone, added_by_clinic=True)
            return redirect('doctor:manage_patients')

        except Exception as exc:
            logger.exception("add_patient failed for name=%r phone=%r by user=%s: %s", name, phone, request.user.username, exc)
            messages.error(request, 'Failed to create patient. Please try again.')
            return render(request, 'doctor/add_patient.html', {'patients': all_patients})

    return render(request, 'doctor/add_patient.html', {'patients': all_patients})


# ─────────────────────────────────────────
# Staff List (billers only)
# ─────────────────────────────────────────

@never_cache
@role_required('doctor')
def staff_view(request):
    billers = InnerMember.objects.filter(role='biller').select_related('user')
    doctors = InnerMember.objects.filter(role='doctor', user__is_active=True).select_related('user')
    pending_doctors = InnerMember.objects.filter(role='doctor', user__is_active=False).select_related('user')
    is_owner = hasattr(request.user, 'innermember') and request.user.innermember.is_owner
    return render(request, 'doctor/staff.html', {
        'billers': billers,
        'doctors': doctors,
        'pending_doctors': pending_doctors,
        'is_owner': is_owner,
    })

# ─────────────────────────────────────────
# Add Staff (biller)
# ─────────────────────────────────────────

@never_cache
@role_required('doctor')
def add_staff(request):

    if request.method != 'POST':
        return JsonResponse({
            'success': False,
            'error': 'Invalid method'
        }, status=405)

    try:
        data = json.loads(request.body)

        name     = data.get('name', '').strip()
        username = data.get('username', '').strip()
        phone    = data.get('phone', '').strip()
        email    = data.get('email', '').strip().lower()
        password = data.get('password', '').strip()

        # Validation
        if not name or not username or not password:
            return JsonResponse({
                'success': False,
                'error': 'Name, username and password are required.'
            }, status=400)

        if User.objects.filter(username=username).exists():
            return JsonResponse({
                'success': False,
                'error': 'Username already taken.'
            }, status=400)

        if email and User.objects.filter(email__iexact=email).exists():
            return JsonResponse({
                'success': False,
                'error': 'Email already in use.'
            }, status=400)

        # Split Name
        parts = name.split(' ', 1)

        first_name = parts[0]
        last_name  = parts[1] if len(parts) > 1 else ''

        # Atomic Transaction
        with transaction.atomic():

            user = User.objects.create_user(
                username=username,
                password=password,
                email=email,
                first_name=first_name,
                last_name=last_name,
            )

            member = InnerMember.objects.create(
                user=user,
                role='biller',
                phone=phone,
            )

        return JsonResponse({
            'success': True,
            'staff': {
                'id': member.id,
                'name': user.get_full_name() or username,
                'username': user.username,
                'email': user.email,
                'phone': member.phone,
                'active': user.is_active,
            }
        })

    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Invalid JSON data.'
        }, status=400)

    except Exception as exc:
        logger.exception("add_staff failed: %s", exc)
        return JsonResponse({
            'success': False,
            'error': 'An unexpected error occurred. Please try again.'
        }, status=500)

# ─────────────────────────────────────────
# Edit Staff
# ─────────────────────────────────────────

@never_cache
@role_required('doctor')
def edit_staff(request, member_id):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid method'})

    try:
        member = get_object_or_404(InnerMember, id=member_id, role__in=['biller', 'doctor'])
        data   = json.loads(request.body)
        is_owner = request.user.innermember.is_owner

        if member.role == 'doctor' and not is_owner:
            return JsonResponse({'success': False, 'error': 'Only the clinic owner can edit doctors.'}, status=403)
        if 'is_default_doctor' in data:
            if not is_owner or member.role != 'doctor':
                return JsonResponse({'success': False, 'error': 'Only the clinic owner can set the default doctor.'}, status=403)
            member.is_default_doctor = data['is_default_doctor'] is True

        name     = data.get('name', '').strip()
        email    = data.get('email', '').strip()
        phone    = data.get('phone', '').strip()
        is_active = data.get('is_active', True)

        if not name:
            return JsonResponse({'success': False, 'error': 'Name is required.'})

        # Email uniqueness check (exclude self)
        if email and User.objects.filter(email=email).exclude(pk=member.user.pk).exists():
            return JsonResponse({'success': False, 'error': 'Email already in use by another user.'})

        parts = name.split(' ', 1)
        member.user.first_name = parts[0]
        member.user.last_name  = parts[1] if len(parts) > 1 else ''
        member.user.email      = email
        member.user.is_active  = is_active
        member.user.save()

        member.phone = phone
        member.save()

        return JsonResponse({'success': True})

    except Exception as exc:
        logger.exception("edit_staff id=%s failed: %s", member_id, exc)
        return JsonResponse({'success': False, 'error': 'An unexpected error occurred.'})


# ─────────────────────────────────────────
# Reset Staff Password
# ─────────────────────────────────────────

@never_cache
@role_required('doctor')
def reset_staff_password(request, member_id):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid method'})

    try:
        member   = get_object_or_404(InnerMember, id=member_id, role='biller')
        data     = json.loads(request.body)
        password = data.get('password', '').strip()

        if not password or len(password) < 6:
            return JsonResponse({'success': False, 'error': 'Password must be at least 6 characters.'})

        # make_password uses hashed format, set_password does the same
        member.user.set_password(password)   # auto hashes
        member.user.save()

        return JsonResponse({'success': True})

    except Exception as exc:
        logger.exception("reset_staff_password id=%s failed: %s", member_id, exc)
        return JsonResponse({'success': False, 'error': 'An unexpected error occurred.'})


# ─────────────────────────────────────────
# Delete Staff
# ─────────────────────────────────────────

@never_cache
@role_required('doctor')
def delete_staff(request, member_id):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid method'})

    try:
        member = get_object_or_404(InnerMember, id=member_id, role='biller')
        member.user.delete()   # cascades → InnerMember will also be deleted
        return JsonResponse({'success': True})

    except Exception as exc:
        logger.exception("delete_staff id=%s failed: %s", member_id, exc)
        return JsonResponse({'success': False, 'error': 'An unexpected error occurred.'})

@never_cache
@role_required('doctor')
def edit_family(request, hid):
    from . import hashid as _hashid
    try:
        member_id = _hashid.decode_hash(hid)
    except Exception:
        return get_object_or_404(FamilyMember, id=0)

    member = get_object_or_404(FamilyMember, id=member_id)

    if request.method == 'POST':
        name     = request.POST.get('name', '').strip()
        phone    = request.POST.get('phone', '').strip()
        relation = request.POST.get('relation', '').strip()
        gender   = request.POST.get('gender', '')
        dob      = request.POST.get('dob')
        bld_grop = request.POST.get('bld_grop')

        # Validate required fields
        if not name:
            messages.error(request, 'Name is required.')
            return render(request, 'doctor/edit_family.html', {'member': member})

        # Check for duplicate phone (exclude self)
        if phone and FamilyMember.objects.filter(phone=phone).exclude(pk=member.pk).exists():
            messages.error(request, 'This phone number is already registered.')
            return render(request, 'doctor/edit_family.html', {'member': member})

        # Update member
        member.name     = name
        member.phone    = phone if phone else None
        member.relation = relation
        member.gender   = gender if gender else None
        member.dob      = dob if dob else None
        member.bld_grop = bld_grop if bld_grop else None
        member.save()

        return redirect('doctor:manage_patients')

    return render(request, 'doctor/edit_family.html', {'member': member})

@never_cache
@role_required('doctor')
def delete_family(request, hid):
    from . import hashid as _hashid
    try:
        member_id = _hashid.decode_hash(hid)
    except Exception:
        return get_object_or_404(FamilyMember, id=0)

    member = get_object_or_404(FamilyMember, id=member_id)

    if request.method == 'POST':
        member.delete()
    return redirect('doctor:manage_patients')

from .models import DoctorLeave
from clinic.models import ClinicSettings
from appointment.models import Appointment
from django.db.models import Q

@login_required(login_url='doctor:login')
@role_required('doctor')
def leave_appointment_preview(request):
    if request.method != 'GET':
        return JsonResponse({'error': 'Invalid method.'}, status=405)

    try:
        start_date = date.fromisoformat(request.GET.get('from_date', ''))
        end_date = date.fromisoformat(request.GET.get('to_date', ''))
    except (TypeError, ValueError):
        return JsonResponse({'error': 'Please choose a valid date range.'}, status=400)

    day_count = (end_date - start_date).days + 1
    if start_date < timezone.localdate():
        return JsonResponse({'error': 'Leave cannot be added for a past date.'}, status=400)
    if day_count < 1 or day_count > 60:
        return JsonResponse({'error': 'Please choose a valid range of up to 60 days.'}, status=400)

    leave_type = request.GET.get('leave_type')
    if leave_type not in dict(DoctorLeave.LEAVE_CHOICES):
        return JsonResponse({'error': 'Please select a leave type.'}, status=400)

    doctor = get_default_doctor()
    existing_dates = DoctorLeave.objects.filter(
        doctor=doctor,
        date__range=(start_date, end_date),
    ).values_list('date', flat=True)
    dates_without_leave = [
        start_date + timedelta(days=offset)
        for offset in range(day_count)
        if start_date + timedelta(days=offset) not in existing_dates
    ]

    appointments = Appointment.objects.filter(
        doctor=doctor,
        appointment_date__in=dates_without_leave,
        status__in=['pending', 'confirmed'],
        is_archived=False,
    ).select_related('patient__user', 'family_member').order_by('appointment_date', 'time_slot')

    clinic = ClinicSettings.objects.first()
    if not clinic or not clinic.lunch_start:
        appointments = appointments.none()
    elif leave_type == 'first_half':
        appointments = appointments.filter(time_slot__lt=clinic.lunch_start)
    elif leave_type == 'second_half':
        appointments = appointments.filter(time_slot__gte=clinic.lunch_start)

    count = appointments.count()
    preview = []
    for appointment in appointments[:10]:
        patient_name = (
            appointment.family_member.name
            if appointment.family_member_id
            else appointment.patient.user.get_full_name() or appointment.patient.user.username
        )
        preview.append({
            'patient': patient_name,
            'date': appointment.appointment_date.strftime('%d %b %Y'),
            'time': appointment.time_slot.strftime('%I:%M %p').lstrip('0'),
        })

    return JsonResponse({
        'count': count,
        'appointments': preview,
        'more': max(count - len(preview), 0),
    })


@login_required(login_url='doctor:login')
@role_required('doctor')
def manage_leaves(request):
    doctor = get_default_doctor()
    leaves = DoctorLeave.objects.filter(doctor=doctor).order_by('-date')

    if request.method == 'POST':
        start_date = request.POST.get('from_date')
        end_date = request.POST.get('to_date') or start_date
        leave_type = request.POST.get('leave_type')
        reason = request.POST.get('reason')

        try:
            start_date = date.fromisoformat(start_date)
            end_date = date.fromisoformat(end_date)
        except (TypeError, ValueError):
            messages.error(request, 'Please enter a valid leave date range.')
            return redirect('doctor:manage_leaves')

        day_count = (end_date - start_date).days + 1
        if start_date < timezone.localdate():
            messages.error(request, 'Leave cannot be added for a past date')
            return redirect('doctor:manage_leaves')
        if day_count < 1:
            messages.error(request, 'To date cannot be before From date.')
            return redirect('doctor:manage_leaves')
        if day_count > 60:
            messages.error(request, 'A leave range cannot exceed 60 days.')
            return redirect('doctor:manage_leaves')

        dates = [start_date + timedelta(days=offset) for offset in range(day_count)]
        added_dates = []
        cancelled_count = 0
        clinic = ClinicSettings.objects.first()

        for leave_date in dates:
            _, created = DoctorLeave.objects.get_or_create(
                doctor=doctor,
                date=leave_date,
                defaults={'leave_type': leave_type, 'reason': reason},
            )
            if not created:
                continue
            added_dates.append(leave_date)

            # Cancel overlapping appointments using the same half-day rules as single-day leave.
            if clinic and clinic.lunch_start:
                overlapping = Appointment.objects.filter(
                    doctor=doctor,
                    appointment_date=leave_date,
                    status__in=['pending', 'confirmed'],
                    is_archived=False,
                )
                if leave_type == 'first_half':
                    overlapping = overlapping.filter(time_slot__lt=clinic.lunch_start)
                elif leave_type == 'second_half':
                    overlapping = overlapping.filter(time_slot__gte=clinic.lunch_start)
                cancelled_count += overlapping.count()
                overlapping.update(status='cancelled', cancellation_reason=reason)

        if added_dates:
            if start_date == end_date:
                date_label = f'{start_date.day} {start_date.strftime("%b")}'
            elif start_date.year == end_date.year and start_date.month == end_date.month:
                date_label = f'{start_date.day}–{end_date.day} {end_date.strftime("%b")}'
            else:
                date_label = f'{start_date.day} {start_date.strftime("%b")}–{end_date.day} {end_date.strftime("%b")}'
                if start_date.year != end_date.year:
                    date_label = f'{start_date.day} {start_date.strftime("%b %Y")}–{end_date.day} {end_date.strftime("%b %Y")}'
            msg = f"Leave added for {len(added_dates)} {'day' if len(added_dates) == 1 else 'days'} ({date_label})."
            if len(added_dates) != day_count:
                msg += ' Existing leave dates were skipped.'
            if cancelled_count:
                msg += f' {cancelled_count} appointment(s) were automatically cancelled.'
            elif not (clinic and clinic.lunch_start):
                msg += ' Please set clinic lunch time in settings for accurate half-day tracking.'
            messages.success(request, msg)
        else:
            messages.warning(request, 'Leave already exists for all selected dates.')
            
        return redirect('doctor:manage_leaves')

    return render(request, 'doctor/manage_leaves.html', {
        'leaves': leaves,
        'today': timezone.localdate(),
    })


@login_required(login_url='doctor:login')
@role_required('doctor')
def delete_leave(request, pk):
    doctor = get_default_doctor()
    leave = get_object_or_404(DoctorLeave, pk=pk, doctor=doctor)
    if request.method == 'POST':
        leave.delete()
        messages.success(request, "Leave deleted successfully.")
    return redirect('doctor:manage_leaves')

@never_cache
@role_required('doctor')
def old_data_upload(request):
    if request.method == 'POST':
        patient_id = request.POST.get('patient_id')
        family_member_id = request.POST.get('family_member_id')
        file = request.FILES.get('document')

        if not patient_id or not file:
            messages.error(request, 'Patient and document are required.')
            return redirect('doctor:old_data_upload')
        try:
            original_name = validate_uploaded_document(file)
        except ValidationError as e:
            messages.error(request, '; '.join(e.messages))
            return redirect('doctor:old_data_upload')

        try:
            if patient_id == 'family_only' and family_member_id:
                family_member = get_object_or_404(FamilyMember, id=family_member_id)
                patient = family_member.patient
            else:
                patient = get_object_or_404(Patient, id=patient_id)
                family_member = None
                
            PatientOldDocument.objects.create(
                patient=patient,
                family_member=family_member,
                file=file,
                original_name=original_name,
                uploaded_by=request.user
            )
            messages.success(request, 'Old data document uploaded successfully.')
            
            from . import hashid as _hashid
            if family_member:
                return redirect('doctor:view_patient', type='family', hid=_hashid.encode_id(family_member.id))
            else:
                return redirect('doctor:view_patient', type='main', hid=_hashid.encode_id(patient.id))
                
        except Exception as e:
            messages.error(request, f"Error uploading document: {str(e)}")
            return redirect('doctor:old_data_upload')
            
    return render(request, 'doctor/old_data.html')

@require_POST
@login_required(login_url='login')
def delete_old_document(request, hid):
    try:
        from doctor import hashid as _hashid
        doc_id = _hashid.decode_hash(hid)
        document = PatientOldDocument.objects.get(id=doc_id)
        
        # Only allow deleting if they are doctor or it belongs to them
        if hasattr(request.user, 'innermember') and request.user.innermember.role == 'doctor':
            document.delete()
            return JsonResponse({'success': True})
        else:
            return JsonResponse({'success': False, 'error': 'Unauthorized'}, status=403)
            
    except PatientOldDocument.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Document not found'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


# ─────────────────────────────────────────
# Patient Feedback
# ─────────────────────────────────────────

from accounts.models import PatientFeedback

@never_cache
@role_required('doctor')
def feedback_list(request):
    feedbacks = PatientFeedback.objects.only(
        'id',
        'name',
        'email',
        'phone',
        'rating',
        'message',
        'is_read',
        'created_at',
    )

    stats = feedbacks.aggregate(
        total_count=Count('id'),
        unread_count=Count('id', filter=Q(is_read=False)),
        avg_rating=Avg('rating'),
    )
    unread_ids = list(
        feedbacks.filter(is_read=False).values_list('id', flat=True)
    )

    if unread_ids:
        PatientFeedback.objects.filter(id__in=unread_ids).update(is_read=True)

    paginator = Paginator(feedbacks, 10)
    page_obj = paginator.get_page(request.GET.get('page'))

    page_range = [
        {
            'label': page_number,
            'number': page_number if isinstance(page_number, int) else None,
            'is_current': page_number == page_obj.number,
            'is_ellipsis': page_number == paginator.ELLIPSIS,
        }
        for page_number in paginator.get_elided_page_range(
            number=page_obj.number,
            on_each_side=1,
            on_ends=1,
        )
    ]

    return render(request, 'doctor/feedback.html', {
        'feedbacks': page_obj,
        'page_obj': page_obj,
        'page_range': page_range,
        'total_count': stats['total_count'],
        'unread_count': stats['unread_count'],
        'avg_rating': stats['avg_rating'],
        'unread_ids': unread_ids,
    })


@never_cache
@require_POST
@role_required('doctor')
def delete_feedback(request, pk):
    try:
        feedback = get_object_or_404(PatientFeedback, pk=pk)
        feedback.delete()
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)

@never_cache
@require_POST
@role_required('doctor')
def bulk_delete_feedback(request):
    try:
        data = json.loads(request.body)
        feedback_ids = data.get('feedback_ids', [])
        if not feedback_ids:
            return JsonResponse({'success': False, 'error': 'No feedback selected.'})
            
        feedbacks = PatientFeedback.objects.filter(id__in=feedback_ids)
        actual_count = feedbacks.count()
        feedbacks.delete()
        
        return JsonResponse({'success': True, 'message': f'{actual_count} feedback(s) deleted successfully.'})
    except Exception as e:
        logger.error(f"Error in bulk delete feedback: {e}")
        return JsonResponse({'success': False, 'error': 'An error occurred during deletion.'})

@never_cache
@role_required('doctor')
def my_profile(request):
    member = get_object_or_404(InnerMember, user=request.user)
    
    if request.method == 'POST':
        if 'remove_profile_picture' in request.POST:
            if member.profile_picture:
                try:
                    member.profile_picture.delete(save=False)
                except Exception:
                    logger.warning("Failed to delete profile picture file for member %s", member.pk)
            member.profile_picture = None
            member.save(update_fields=['profile_picture'])
            messages.success(request, 'Profile picture removed successfully.')
            return redirect('doctor:my_profile')

        if 'update_profile' in request.POST:
            first_name = request.POST.get('first_name', '').strip()
            last_name = request.POST.get('last_name', '').strip()
            username = request.POST.get('username', '').strip()
            email = request.POST.get('email', '').strip().lower()
            phone = request.POST.get('phone', '').strip()
            
            # Check for unique username and email
            if username and User.objects.filter(username=username).exclude(pk=request.user.pk).exists():
                messages.error(request, 'Username already exists.')
                return redirect('doctor:my_profile')
                
            if email and User.objects.filter(email__iexact=email).exclude(pk=request.user.pk).exists():
                messages.error(request, 'Email already exists.')
                return redirect('doctor:my_profile')
            
            request.user.username = username
            request.user.email = email
            request.user.first_name = first_name
            request.user.last_name = last_name
            request.user.save()
            
            member.phone = phone
            old_picture = member.profile_picture
            if 'profile_picture' in request.FILES:
                if old_picture:
                    try:
                        old_picture.delete(save=False)
                    except Exception:
                        logger.warning("Failed to delete previous profile picture file for member %s", member.pk)
                member.profile_picture = request.FILES['profile_picture']
            member.save()
            
            messages.success(request, 'Profile updated successfully.')
            return redirect('doctor:my_profile')
            
        elif 'change_password' in request.POST:
            current_password = request.POST.get('current_password', '')
            new_password = request.POST.get('new_password', '')
            confirm_password = request.POST.get('confirm_password', '')
            
            if not request.user.check_password(current_password):
                messages.error(request, 'Incorrect current password.')
            elif new_password != confirm_password:
                messages.error(request, 'New passwords do not match.')
            elif len(new_password) < 6:
                messages.error(request, 'Password must be at least 6 characters.')
            else:
                request.user.set_password(new_password)
                request.user.save()
                from django.contrib.auth import update_session_auth_hash
                update_session_auth_hash(request, request.user)
                messages.success(request, 'Password changed successfully.')
            return redirect('doctor:my_profile')
            
    return render(request, 'doctor/my_profile.html', {'member': member})


@never_cache
def register_view(request):
    # Only redirect if they are actually a logged-in doctor/staff
    if request.user.is_authenticated:
        try:
            if request.user.innermember:
                return redirect('doctor:dashboard')
        except:
            pass

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        username = request.POST.get('username', '').strip()
        email = request.POST.get('email', '').strip().lower()
        phone = request.POST.get('phone', '').strip()
        password = request.POST.get('password', '')
        confirm_password = request.POST.get('confirm_password', '')

        if not all([name, username, email, phone, password, confirm_password]):
            return render(request, 'doctor/register.html', {'error': 'All fields are required.'})
        
        if password != confirm_password:
            return render(request, 'doctor/register.html', {'error': 'Passwords do not match.'})
            
        if not phone.isdigit() or len(phone) != 10:
            return render(request, 'doctor/register.html', {'error': 'Phone must be exactly 10 digits.'})
            
        if User.objects.filter(username=username).exists():
            return render(request, 'doctor/register.html', {'error': 'Username already exists.'})
            
        if User.objects.filter(email__iexact=email).exists():
            return render(request, 'doctor/register.html', {'error': 'Email already in use.'})
            
        from django.contrib.auth.password_validation import validate_password
        from django.core.exceptions import ValidationError
        try:
            validate_password(password)
        except ValidationError as e:
            return render(request, 'doctor/register.html', {'error': ' '.join(e.messages)})

        name_parts = name.split(' ', 1)
        first_name = name_parts[0]
        last_name = name_parts[1] if len(name_parts) > 1 else ''

        try:
            with transaction.atomic():
                user = User.objects.create_user(
                    username=username,
                    password=password,
                    email=email,
                    first_name=first_name,
                    last_name=last_name,
                    is_active=False
                )
                
                # Find owner doctor if exists
                owner = InnerMember.objects.filter(role='doctor', is_owner=True).first()
                owner_user = owner.user if owner else None
                
                InnerMember.objects.create(
                    user=user,
                    role='doctor',
                    is_owner=False,
                    phone=phone,
                    doctor=owner_user
                )
                
            messages.success(request, 'Registration submitted. You can log in after the clinic owner approves your account.')
            return redirect('doctor:login')
        except Exception as e:
            return render(request, 'doctor/register.html', {'error': 'Registration failed. Please try again.'})

    return render(request, 'doctor/register.html')

@require_POST
@role_required('doctor')
def approve_doctor(request, member_id):
    if not hasattr(request.user, 'innermember') or not request.user.innermember.is_owner:
        return JsonResponse({'success': False, 'error': 'Permission denied.'}, status=403)
        
    try:
        member = InnerMember.objects.get(id=member_id)
        member.user.is_active = True
        member.user.save()
        return JsonResponse({'success': True})
    except InnerMember.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Member not found.'})

@require_POST
@role_required('doctor')
def reject_doctor(request, member_id):
    if not hasattr(request.user, 'innermember') or not request.user.innermember.is_owner:
        return JsonResponse({'success': False, 'error': 'Permission denied.'}, status=403)
        
    try:
        member = InnerMember.objects.get(id=member_id)
        member.user.delete()
        return JsonResponse({'success': True})
    except InnerMember.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Member not found.'})


@never_cache
@login_required
@owner_required
def import_patients(request):
    """
    3-step patient import:
    1. GET: upload form
    2. POST file: parse & validate without writing to DB, show preview & summary
    3. POST confirm: create records for 'New' rows, re-checking duplicates at save time
    """
    import csv
    from django.http import HttpResponse
    from .forms import PatientImportForm
    from accounts.services.patient_import import (
        parse_import_file,
        validate_patient_rows,
        create_patients_from_rows,
    )

    step = "upload"
    summary = None
    preview_rows = None

    if request.method == "POST":
        action = request.POST.get("action", "")

        if action == "upload":
            form = PatientImportForm(request.POST, request.FILES)
            if form.is_valid():
                uploaded_file = form.cleaned_data["file"]
                try:
                    raw_rows = parse_import_file(uploaded_file)
                    if not raw_rows:
                        messages.error(request, "The uploaded file contains no data rows.")
                        return redirect("doctor:import_patients")

                    validated_rows = validate_patient_rows(raw_rows)

                    new_count = sum(1 for r in validated_rows if r["status"] == "New")
                    dup_count = sum(1 for r in validated_rows if r["status"] == "Duplicate")
                    err_count = sum(1 for r in validated_rows if r["status"] == "Error")

                    summary = {
                        "total": len(validated_rows),
                        "new": new_count,
                        "duplicate": dup_count,
                        "error": err_count,
                    }

                    # Store parsed rows in session for confirmation
                    request.session["patient_import_rows"] = validated_rows
                    request.session["patient_import_summary"] = summary
                    preview_rows = validated_rows
                    step = "preview"

                except Exception as e:
                    logger.exception("Failed to parse patient import file: %s", e)
                    messages.error(request, f"Failed to process file: {str(e)}")
                    return redirect("doctor:import_patients")
            else:
                step = "upload"

        elif action == "confirm":
            parsed_rows = request.session.get("patient_import_rows")
            if not parsed_rows:
                messages.error(request, "No import session found. Please upload the file again.")
                return redirect("doctor:import_patients")

            results = create_patients_from_rows(parsed_rows, dry_run=False)

            # Store skipped rows in session for download
            request.session["patient_import_skipped"] = results["skipped_rows"]
            # Clear parsed rows from session
            request.session.pop("patient_import_rows", None)
            request.session.pop("patient_import_summary", None)

            summary = {
                "total": results["total"],
                "created": results["created_count"],
                "duplicate": results["duplicate_count"],
                "error": results["error_count"],
                "skipped_count": len(results["skipped_rows"]),
            }
            step = "done"

        elif action == "cancel":
            request.session.pop("patient_import_rows", None)
            request.session.pop("patient_import_summary", None)
            messages.info(request, "Import cancelled.")
            return redirect("doctor:import_patients")

    else:
        form = PatientImportForm()
        # Clean up any leftover unconfirmed import rows on fresh GET
        request.session.pop("patient_import_rows", None)
        request.session.pop("patient_import_summary", None)

    return render(request, "doctor/import_patients.html", {
        "form": form if step == "upload" else None,
        "step": step,
        "summary": summary,
        "preview_rows": preview_rows,
    })


@never_cache
@login_required
@owner_required
def import_patients_sample(request):
    """
    Downloads sample CSV for patient import.
    """
    from django.http import HttpResponse
    from accounts.services.patient_import import generate_sample_csv

    csv_data = generate_sample_csv()
    response = HttpResponse(csv_data, content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="patient_import_sample.csv"'
    return response


@never_cache
@login_required
@owner_required
def import_patients_skipped(request):
    """
    Downloads CSV of skipped rows (duplicates, errors) from the last import.
    """
    import csv
    import io
    from django.http import HttpResponse

    skipped_rows = request.session.get("patient_import_skipped", [])
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["row_num", "name", "phone", "email", "gender", "dob", "blood_group", "address", "status", "reason"])

    for r in skipped_rows:
        writer.writerow([
            r.get("row_num", ""),
            r.get("name", ""),
            r.get("phone", ""),
            r.get("email", ""),
            r.get("gender", ""),
            r.get("dob", ""),
            r.get("blood_group", ""),
            r.get("address", ""),
            r.get("status", ""),
            r.get("reason", ""),
        ])

    response = HttpResponse(output.getvalue(), content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="skipped_patients.csv"'
    return response


