from django.shortcuts import render,redirect
from django.contrib.auth import authenticate,login,logout
from django.contrib.auth.decorators import login_required
from django.views.decorators.cache import never_cache
from .decorators import role_required
from .models import InnerMember
# Create your views here.

from django.contrib.auth import authenticate, login
from django.shortcuts import render, redirect
from .models import InnerMember

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

            # 🔥 YAHAN CHANGE
            if role == 'doctor':
                return redirect('doctor:dashboard')
            else:
                return redirect('doctor:billing')

        else:
            return render(request, 'doctor/login.html', {'error': 'Invalid credentials'})

    return render(request, 'doctor/login.html')

# Logout 
def logout_view(request):
     logout(request)
     return redirect('doctor:login')


@never_cache
@role_required('doctor')
def dashboard(request):
     return render(request, 'doctor/dashboard.html')


@never_cache
@login_required
def manage_patients(request):
     return render(request, 'doctor/manage_patients.html')


@never_cache    
@login_required
def add_patient(request):
     return render(request, 'doctor/add_patient.html')



@never_cache
@login_required
def prescription(request):
     return render(request, 'doctor/prescription.html')



@never_cache
@login_required
def billing(request):
     return render(request, 'doctor/billing.html')