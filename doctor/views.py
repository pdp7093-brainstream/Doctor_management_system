import json
import logging

from django.shortcuts import render, redirect, get_object_or_404
from django.db import OperationalError, ProgrammingError, transaction
from django.contrib.auth import authenticate, login, logout as auth_logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.views.decorators.cache import never_cache
from django.views import View
from .decorators import role_required
from .models import InnerMember
from appointment.models import Appointment, LabDocument, PatientUploadedDocument, PatientOldDocument
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.http import require_POST
from django.http import JsonResponse
from accounts.models import Patient
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db.models import Avg, Count, Q
from django.core.paginator import Paginator
from accounts.models import FamilyMember
from appointment.file_validation import validate_uploaded_document

logger = logging.getLogger(__name__)

def login_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')

        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)

            try:
                member = InnerMember.objects.get(user=user)
                role = member.role

            except InnerMember.DoesNotExist:
                return render(request, 'doctor/login.html', {'error': 'Role not assigned'})

            # YAHAN CHANGE
            if role == 'doctor':
                return redirect('doctor:dashboard')
            else:
                return redirect('billing:bill_list')

        else:
            return render(request, 'doctor/login.html', {'error': 'Invalid credentials'})

    return render(request, 'doctor/login.html')

# Logout 
def logout_view(request):
    auth_logout(request)
    return render(request,'doctor/login.html')

@method_decorator([never_cache, role_required("doctor")], name="dispatch")
class DashboardView(View):
    def get(self, request):
        today  = timezone.localdate()

        # Show all appointments for today so doctor can handle any booked slot.
        # This includes appointments booked by patients and unassigned doctor slots.
        today_appointments = Appointment.objects.filter(
            appointment_date=today,
            is_archived=False
        ).select_related('patient__user', 'family_member', 'doctor__user', 'booked_by').order_by('time_slot')

        today_counts = Appointment.objects.filter(
            appointment_date=today,
            is_archived=False
        ).aggregate(
            total=Count('id'),
            remaining_today=Count('id', filter=Q(status='pending')),
        )
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
    today_counts = Appointment.objects.filter(
        appointment_date=today,
        is_archived=False
    ).aggregate(
        total=Count('id'),
        remaining_today=Count('id', filter=Q(status='pending')),
    )
    
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
            'type': 'main'
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
def edit_patient(request, hid):
    from . import hashid as _hashid
    try:
        patient_id = _hashid.decode_hash(hid)
    except Exception:
        return get_object_or_404(Patient, id=0)

    patient = get_object_or_404(Patient, pk=patient_id)

    if request.method == 'POST':

        name      = request.POST.get('name', '').strip()
        email     = request.POST.get('email', '').strip()
        dob       = request.POST.get('dob')
        gender    = request.POST.get('gender')
        phone     = request.POST.get('phone', '').strip()
        bld_grop  = request.POST.get('bld_grop')
        address   = request.POST.get('address')

        # EMAIL DUPLICATE CHECK
        if email and User.objects.filter(email=email).exclude(pk=patient.user.pk).exists():

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
        email     = request.POST.get('email', '').strip()
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
        if not phone:
           
            return render(request, 'doctor/add_patient.html', {'patients': all_patients})

        if User.objects.filter(username=phone).exists():

            return render(request, 'doctor/add_patient.html', {'patients': all_patients})

        name_parts = name.split(' ', 1)
        first_name = name_parts[0]
        last_name  = name_parts[1] if len(name_parts) > 1 else ''

        try:
            with transaction.atomic():
                user = User.objects.create_user(
                    username   = phone,        # phone as username
                    password   = 'password@123',      # default password = phone
                    email      = email or '',
                    first_name = first_name,
                    last_name  = last_name,
                )
                # The Patient object is auto-created via a post_save signal on the User model.
                # So we fetch it and update it, rather than creating a duplicate.
                patient = user.patient
                patient.phone    = phone
                patient.address  = address
                patient.dob      = dob or None
                patient.gender   = gender or None
                patient.bld_grop = bld_grop or None
                patient.save()

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
    return render(request, 'doctor/staff.html', {'billers': billers})


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
        email    = data.get('email', '').strip()
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

        if email and User.objects.filter(email=email).exists():
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
        member = get_object_or_404(InnerMember, id=member_id, role='biller')
        data   = json.loads(request.body)

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
def manage_leaves(request):
    doctor = request.user.innermember
    leaves = DoctorLeave.objects.filter(doctor=doctor).order_by('-date')

    if request.method == 'POST':
        date = request.POST.get('date')
        leave_type = request.POST.get('leave_type')
        reason = request.POST.get('reason')

        if DoctorLeave.objects.filter(doctor=doctor, date=date).exists():
            messages.error(request, f"Leave already exists for {date}.")
        else:
            leave = DoctorLeave.objects.create(
                doctor=doctor,
                date=date,
                leave_type=leave_type,
                reason=reason
            )
            
            # Cancel overlapping appointments
            clinic = ClinicSettings.objects.first()
            if clinic and clinic.lunch_start:
                lunch_time = clinic.lunch_start
                overlapping = Appointment.objects.filter(
                    doctor=doctor,
                    appointment_date=date,
                    status__in=['pending', 'confirmed'],
                    is_archived=False
                )
                
                if leave_type == 'first_half':
                    overlapping = overlapping.filter(time_slot__lt=lunch_time)
                elif leave_type == 'second_half':
                    overlapping = overlapping.filter(time_slot__gte=lunch_time)
                
                count = overlapping.count()
                overlapping.update(status='cancelled', cancellation_reason=reason)
                
                msg = "Leave added successfully."
                if count > 0:
                    msg += f" {count} appointment(s) were automatically cancelled."
                messages.success(request, msg)
            else:
                messages.success(request, "Leave added successfully. (Note: Please set clinic lunch time in settings for accurate half-day tracking).")
            
        return redirect('doctor:manage_leaves')

    return render(request, 'doctor/manage_leaves.html', {'leaves': leaves})


@login_required(login_url='doctor:login')
@role_required('doctor')
def delete_leave(request, pk):
    doctor = request.user.innermember
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
@login_required(login_url='doctor:login')
def my_profile(request):
    member = get_object_or_404(InnerMember, user=request.user)
    
    if request.method == 'POST':
        if 'update_profile' in request.POST:
            first_name = request.POST.get('first_name', '').strip()
            last_name = request.POST.get('last_name', '').strip()
            username = request.POST.get('username', '').strip()
            email = request.POST.get('email', '').strip()
            phone = request.POST.get('phone', '').strip()
            
            # Check for unique username and email
            if username and User.objects.filter(username=username).exclude(pk=request.user.pk).exists():
                messages.error(request, 'Username already exists.')
                return redirect('doctor:my_profile')
                
            if email and User.objects.filter(email=email).exclude(pk=request.user.pk).exists():
                messages.error(request, 'Email already exists.')
                return redirect('doctor:my_profile')
            
            request.user.username = username
            request.user.email = email
            request.user.first_name = first_name
            request.user.last_name = last_name
            request.user.save()
            
            member.phone = phone
            if 'profile_picture' in request.FILES:
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
