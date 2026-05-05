import json
from .models import *
from .forms import *
from django.http import JsonResponse
from django.shortcuts import render, redirect,get_object_or_404
from django.contrib.auth.models import User
from django.contrib.auth import authenticate,logout as auth_logout, login as auth_login,update_session_auth_hash
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from appointment.models import Appointment

def home(request):
    return render(request, 'index.html')

def about(request):
    return render(request,'about.html')

def departments(request):
    return render(request,'departments.html')

def services(request):
    return render(request,'services.html')

def terms(request):
    return render(request,'terms.html')

def contact(request):
    return render(request,'contact.html')

def login(request):
    return render(request,'authentication/login.html')


# ─────────────────────────────────────────
# accounts/views.py mein add karo
# ─────────────────────────────────────────
@login_required
def add_family_member(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid method'})

    try:
        data     = json.loads(request.body)
        name     = data.get('name', '').strip()
        relation = data.get('relation', '').strip()
        phone    = data.get('phone', '').strip()
        gender   = data.get('gender', '').strip()
        dob      = data.get('dob', '').strip() or None
        bld_grop = data.get('bld_grop', '').strip()

        if not name or not relation:
            return JsonResponse({'success': False, 'error': 'Name and relation are required.'})

        patient = request.user.patient

        # Duplicate check
        if FamilyMember.objects.filter(patient=patient, name__iexact=name, relation__iexact=relation).exists():
            return JsonResponse({'success': False, 'error': f'"{name} ({relation})" already added.'})

        member = FamilyMember.objects.create(
            patient  = patient,
            name     = name,
            relation = relation,
            phone    = phone,
            gender   = gender or None,
            dob      = dob,
            bld_grop = bld_grop or None,
        )

        return JsonResponse({
            'success': True,
            'member': {
                'id'      : member.id,
                'name'    : member.name,
                'relation': member.relation,
                'phone'   : member.phone,
            }
        })

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
def update_family_member(request, member_id):
    """AJAX — family member update"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid method'})
    try:
        member = get_object_or_404(FamilyMember, id=member_id, patient=request.user.patient)
        data     = json.loads(request.body)
        name     = data.get('name', '').strip()
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
 
        member.name     = name
        member.relation = relation
        member.gender   = data.get('gender') or None
        member.dob      = data.get('dob') or None
        member.bld_grop = data.get('bld_grop') or None
        member.phone    = data.get('phone', '').strip()
        member.save()
 
        return JsonResponse({'success': True})
 
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})
 
 
@login_required
def delete_family_member(request, member_id):
    """AJAX — family member delete"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid method'})
    try:
        member = get_object_or_404(FamilyMember, id=member_id, patient=request.user.patient)
        member.delete()
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})
 

@login_required(login_url='login')
def dashboard(request):
    appointments = Appointment.objects.filter(patient__user=request.user).select_related('patient__user', 'doctor__user').order_by('-appointment_date', '-time_slot')
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
    Patient.objects.get_or_create(user=request.user)
    family_members = FamilyMember.objects.filter(patient=request.user.patient)
    return render(request, 'pdashboard/profile.html', {
        'family_members': family_members,
    })

#Authentication

class SignupView(View):
    def get(self, request):
        form = RegistrationForm()
        return render(request, 'authentication/register.html', {'form': form})

    def post(self, request):
        form = RegistrationForm(request.POST)
        if form.is_valid():
            name = form.cleaned_data['name']
            phone = form.cleaned_data['phone']
            password = form.cleaned_data['password']

            user = User.objects.create_user(
                username=phone,
                password=password,
                first_name=name
            )

            Patient.objects.create(
                user=user,
                phone=phone
            )

            # important fix
            user = authenticate(request, username=phone, password=password)
            if user is not None:
                auth_login(request, user)

            return redirect('login')

        return render(request, 'authentication/register.html', {'form': form})


class LoginView(View):
    def get(self, request):
        return render(request, 'authentication/login.html')

    def post(self, request):
        phone = request.POST.get('phone')      
        password = request.POST.get('password')

        # Phone number as username authenticate karo
        user = authenticate(request, username=phone, password=password)

        if user is not None:
            auth_login(request, user)
            return redirect('index')
        else:
            return render(request, 'authentication/login.html', {'error': 'Invalid phone or password'})


# --- LOGOUT VIEW (Optional but recommended) ---
def logout_view(request):
    auth_logout(request)
    return redirect('index')


class ChangePasswordView(LoginRequiredMixin, View):
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
                # Zaroori: Isse password change hone ke baad session logout nahi hoga
                update_session_auth_hash(request, user)
                messages.success(request, 'Your password was successfully updated!')
                return redirect('profile')
            else:
                messages.error(request, 'The old password you entered is incorrect.')
        
        return render(request, 'authentication/change_password.html', {'form': form})

# Update user profile

@login_required
def profile_settings(request):
    user = request.user
    patient, created = Patient.objects.get_or_create(user=user)

    if request.method == 'POST':
        
        user.first_name = request.POST.get('first_name')
        user.email = request.POST.get('email')
        user.save()

        
        patient.phone = request.POST.get('phone')
        patient.address = request.POST.get('address')
        patient.dob = request.POST.get('dob') or None
        patient.gender = request.POST.get('gender') or None
        patient.bld_grop = request.POST.get('bld_grop') or None
        
        # Handle Profile Picture Upload
        if 'profile_picture' in request.FILES:
            patient.profile_picture = request.FILES['profile_picture']
        
        patient.save()

        messages.success(request, "Profile updated successfully!")
        return redirect('profile') # Wapas profile page par bhej dein

    return render(request, 'authentication/profile.html')