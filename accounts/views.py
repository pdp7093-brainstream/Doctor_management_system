import json
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
from appointment.models import Appointment

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

def contact(request):
    return render(request, 'contact.html')

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
def update_family_member(request, member_id):
    """Update family member via AJAX"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid method'})
    
    try:
        member = get_object_or_404(FamilyMember, id=member_id, patient=request.user.patient)
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
        ).exclude(id=member_id).exists():
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
def delete_family_member(request, member_id):
    """Delete family member via AJAX"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid method'})
    
    try:
        member = get_object_or_404(FamilyMember, id=member_id, patient=request.user.patient)
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


class LoginView(View):

    template_name = 'authentication/login.html'

    def get(self, request):
        return render(request, self.template_name)

    def post(self, request):

        # Fast input fetch
        phone = request.POST.get('phone', '').strip()
        password = request.POST.get('password', '').strip()

        # Validation
        if not phone or not password:
            return render(request, self.template_name, {
                'error': 'Phone and password are required.'
            })

        # Clean phone once
        cleaned_phone = re.sub(r'\D', '', phone)

        try:
            # SINGLE OPTIMIZED QUERY
            patient = (
                Patient.objects
                .select_related('user')
                .only('phone', 'user__username', 'user__password')
                .get(phone=cleaned_phone)
            )

        except Patient.DoesNotExist:
            return render(request, self.template_name, {
                'error': 'Invalid phone number or password.'
            })

        # Authenticate
        user = authenticate(
            request,
            username=patient.user.username,
            password=password
        )

        if user is None:
            return render(request, self.template_name, {
                'error': 'Invalid phone number or password.'
            })

        # Login
        auth_login(request, user)

        return redirect('dashboard')

def logout_view(request):
    """Logout user"""
    auth_logout(request)
    return redirect('login')


# ═════════════════════════════════════════════════════════════
# PROFILE VIEWS
# ═════════════════════════════════════════════════════════════

@login_required(login_url='login')
def dashboard(request):
    """Patient dashboard"""
    appointments = Appointment.objects.filter(
        patient__user=request.user
    ).select_related('patient__user', 'doctor__user').order_by('-appointment_date', '-time_slot')
    
    total_visits = appointments.count()
    pending_appointments = appointments.filter(status='pending').count()
    total_spent = 0

    context = {
        'appointments': appointments,
        'total_visits': total_visits,
        'pending_appointments': pending_appointments,
        'total_spent': total_spent,
    }
    return render(request, 'pdashboard/dashboard.html', context)


@login_required(login_url='login')
def profile(request):
    """Patient profile page"""
    patient, created = Patient.objects.get_or_create(user=request.user)
    family_members = FamilyMember.objects.filter(patient=patient)
    
    return render(request, 'pdashboard/profile.html', {
        'family_members': family_members,
    })


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