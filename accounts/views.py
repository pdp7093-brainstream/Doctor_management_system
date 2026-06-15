import json
import re
import random
from .models import *
from .forms import *
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, logout as auth_logout, login as auth_login, update_session_auth_hash
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from appointment.models import Appointment, LabDocument, PatientUploadedDocument
from doctor.models import InnerMember
from django.core.exceptions import ValidationError
from django.db import OperationalError, ProgrammingError
from django.db.models import Count, Q
from django.core.paginator import Paginator
from django.utils.dateparse import parse_date, parse_time
from appointment.file_validation import validate_uploaded_document

def home(request):
    return render(request, 'index.html')

def about(request):
    return render(request, 'about.html')

def departments(request):
    return render(request, 'departments.html')

def services(request):
    return render(request, 'services.html')

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

    return render(request, 'feedback.html')

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
        member.dob = data.get('dob') or None
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

                # Auto-login after signup
                user = authenticate(request, username=email, password=password)
                if user is not None:
                    auth_login(request, user)
                    
                    return redirect('login')
                else:
                   
                    return redirect('login')

            except Exception as e:
                form.add_error(None, f'Error creating account: {str(e)}')
                return render(request, 'authentication/register.html', {'form': form})

        return render(request, 'authentication/register.html', {'form': form})


@method_decorator(never_cache, name='dispatch')
class LoginView(View):

    template_name = 'authentication/login.html'

    def get(self, request):
        from django.views.decorators.csrf import ensure_csrf_cookie
        response = render(request, self.template_name)
        # Ensure CSRF cookie is always set so AJAX requests can read it
        from django.middleware.csrf import get_token
        get_token(request)
        return response

    def post(self, request):
        from django.urls import reverse
        from django.http import JsonResponse
        import json
        
        is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.content_type == 'application/json'
        
        if request.content_type == 'application/json':
            try:
                data = json.loads(request.body)
            except json.JSONDecodeError:
                data = {}
        else:
            data = request.POST

        if 'otp' in data:
            session_otp = request.session.get('login_otp')
            submitted_otp = str(data.get('otp', '')).strip()
            
            if session_otp and str(session_otp) == submitted_otp:
                # OTP is correct, log in user
                user_id = request.session.get('login_user_id')
                if not user_id:
                    if is_ajax: return JsonResponse({'success': False, 'error': 'Session expired. Please try again.'})
                    return render(request, self.template_name, {'error': 'Session expired. Please try again.'})
                
                try:
                    user = User.objects.get(id=user_id)
                    # When manually logging a user in without authenticate(), we must specify the backend
                    # if multiple authentication backends are configured.
                    auth_login(request, user, backend='django.contrib.auth.backends.ModelBackend')
                    
                    if 'login_otp' in request.session:
                        del request.session['login_otp']
                    if 'login_user_id' in request.session:
                        del request.session['login_user_id']
                        
                    if is_ajax: return JsonResponse({'success': True, 'redirect_url': reverse('profile')})
                    return redirect('profile')
                except User.DoesNotExist:
                    if is_ajax: return JsonResponse({'success': False, 'error': 'User not found. Please try again.'})
                    return render(request, self.template_name, {'error': 'User not found. Please try again.'})
            else:
                if is_ajax: return JsonResponse({'success': False, 'error': 'Invalid OTP. Please try again.'})
                return render(request, self.template_name, {'show_otp': True, 'error': 'Invalid OTP. Please try again.'})

        # Phone input fetch
        phone = data.get('phone', '').strip()

        # Validation
        if not phone:
            if is_ajax: return JsonResponse({'success': False, 'error': 'Phone number is required.'})
            return render(request, self.template_name, {
                'error': 'Phone number is required.'
            })

        # Clean phone once
        cleaned_phone = re.sub(r'\D', '', phone)

        try:
            # SINGLE OPTIMIZED QUERY
            patient = (
                Patient.objects
                .select_related('user')
                .only('phone', 'user__id')
                .get(phone=cleaned_phone)
            )

        except Patient.DoesNotExist:
            if is_ajax: return JsonResponse({'success': False, 'error': 'Phone number not registered. Please Sign Up.'})
            return render(request, self.template_name, {
                'error': 'Phone number not registered.Please Sign Up.'
            })

        # Generate OTP
        import random
        otp = random.randint(100000, 999999)
        
        from django.conf import settings
        if settings.DEBUG:
            print(f"=============================\nOTP for Login ({patient.phone}): {otp}\n=============================")
        
        request.session['login_otp'] = str(otp)
        request.session['login_user_id'] = patient.user.id

        if is_ajax:
            return JsonResponse({'success': True})
        return render(request, self.template_name, {'show_otp': True})

def logout_view(request):
    """Logout user"""
    auth_logout(request)
    return redirect('login')


# ═════════════════════════════════════════════════════════════
# PROFILE VIEWS
# ═════════════════════════════════════════════════════════════

@never_cache
@login_required(login_url='login')
def dashboard(request):
    """Patient dashboard"""
    patient = Patient.objects.get(user=request.user)
    
    base_appointments = Appointment.objects.filter(
        patient__user=request.user,
        is_archived=False
    ).select_related(
        'patient__user',
        'family_member',
        'doctor__user',
        'booked_by',
    )

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
    )

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
        'pending_appointments': appointment_counts['pending_appointments'],
        'total_spent': total_spent,
    }
    return render(request, 'pdashboard/dashboard.html', context)


@never_cache
@login_required(login_url='login')
def profile(request):
    """Patient profile page"""
    patient, created = Patient.objects.get_or_create(user=request.user)
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
    
    return render(request, 'pdashboard/profile.html', {
        'family_members': family_members,
        'lab_documents': lab_documents,
        'uploaded_documents': uploaded_documents,
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

    if request.method == 'POST':
        # Get form data
        first_name = request.POST.get('first_name', '').strip()
        email = request.POST.get('email', '').strip()
        phone = request.POST.get('phone', '').strip()
        address = request.POST.get('address', '').strip() or None
        dob = request.POST.get('dob') or None
        gender = request.POST.get('gender') or None
        bld_grop = request.POST.get('bld_grop') or None

        errors = []

        # Validate phone if provided
        if phone:
            import re
            cleaned_phone = re.sub(r'[\s\-\+\(\)]', '', phone)
            if not re.match(r'^\d{10,15}$', cleaned_phone):
                errors.append('Invalid phone number format.')
            #  Check uniqueness in Patient table (exclude current user's patient)
            elif Patient.objects.filter(phone=cleaned_phone).exclude(user=user).exists():
                errors.append('This phone number is already registered!')
            phone = cleaned_phone

        # Validate email if provided
        if email:
            if User.objects.filter(email=email).exclude(id=user.id).exists():
                errors.append('This email is already in use!')

        if errors:
            for error in errors:
                messages.error(request, error)
            return redirect('profile-setting')

        #  Update User (email as username)
        user.first_name = first_name
        if email and user.email != email:
            # Also update username if email changes
            if not User.objects.filter(username=email).exclude(id=user.id).exists():
                user.username = email
            user.email = email
        user.save()

        #  Update Patient - store phone here
        patient.phone = phone  # Phone goes to Patient table only
        patient.address = address
        patient.dob = dob
        patient.gender = gender
        patient.bld_grop = bld_grop
        
        # Handle profile picture
        if 'profile_picture' in request.FILES:
            patient.profile_picture = request.FILES['profile_picture']
        
        patient.save()

        return redirect('profile')

    return render(request, 'pdashboard/profile.html')


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
