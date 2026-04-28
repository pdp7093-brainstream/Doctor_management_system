from django.shortcuts import render, redirect
from .models import *
from .forms import *
from django.contrib.auth.models import User
from django.contrib.auth import authenticate,logout as auth_logout, login as auth_login
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth import update_session_auth_hash
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile 

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

@login_required(login_url='login')
def dashboard(request):
    return render(request,'pdashboard/dashboard.html')

@login_required(login_url='login')
def profile(request):
    return render(request,'pdashboard/profile.html')

def report(request):
    return render(request,'pdashboard/reports.html')

#Authentication

class SignupView(View):
    def get(self, request):
        form = RegistrationForm()
        return render(request, 'authentication/register.html', {'form': form})

    def post(self, request):
        form = RegistrationForm(request.POST)
        if form.is_valid():
            # Data extraction from cleaned form
            name = form.cleaned_data['name']
            email = form.cleaned_data['email']
            password = form.cleaned_data['password']

        
            # User & Patient Creation
            user = User.objects.create_user(username=email, email=email, password=password, first_name=name)
            Patient.objects.create(
                user=user,
            )
            auth_login(request, user)
            return redirect('login')
        
        # Agar invalid hai toh errors ke saath wapas bhej do
        return render(request, 'authentication/register.html', {'form': form})
    

class LoginView(View):
    def get(self, request):
        return render(request, 'authentication/login.html')

    def post(self, request):
        email = request.POST.get('email')
        password = request.POST.get('password')
        
        user = authenticate(request, username=email, password=password)
        
        if user is not None:
            auth_login(request, user)
            return redirect('index')
        else:
            return render(request, 'authentication/login.html', {'error': 'Invalid credentials'})
        
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

from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import Patient
@login_required
def profile_settings(request):
    user = request.user
    patient = user.patient # Current logged-in user ka patient profile

    if request.method == 'POST':
        # 1. User basic info update karein
        user.first_name = request.POST.get('first_name')
        user.email = request.POST.get('email')
        user.save()

        # 2. Nayi fields jo aapne model mein add kari hain, unhe yahan save karein
        patient.phone = request.POST.get('phone')
        patient.address = request.POST.get('address')
        patient.dob = request.POST.get('dob')
        patient.gender = request.POST.get('gender')
        patient.bld_grop = request.POST.get('bld_grop') # Jo field name models.py mein hai
        
        # Additional fields (Medical History etc.)
        patient.city = request.POST.get('city')
        patient.state = request.POST.get('state')
        patient.pin = request.POST.get('pin')
        patient.diseases = request.POST.get('diseases')
        patient.allergies = request.POST.get('allergies')
        
        # Handle Profile Picture Upload
        if 'profile_picture' in request.FILES:
            patient.profile_picture = request.FILES['profile_picture']
        
        patient.save()

        messages.success(request, "Profile updated successfully!")
        return redirect('profile') # Wapas profile page par bhej dein

    return render(request, 'authentication/profile.html')