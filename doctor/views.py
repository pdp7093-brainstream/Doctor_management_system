from django.shortcuts import render, redirect, get_object_or_404
from django.db import transaction
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.views.decorators.cache import never_cache
from django.views import View
from .decorators import role_required
from .models import InnerMember
from appointment.models import Appointment
from django.utils import timezone
from django.utils.decorators import method_decorator
from accounts.models import Patient
from django.contrib import messages

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
                return redirect('doctor:billing')

        else:
            return render(request, 'doctor/login.html', {'error': 'Invalid credentials'})

    return render(request, 'doctor/login.html')

# Logout 
def logout_view(request):
     logout(request)
     return redirect('doctor:login')

@method_decorator(login_required(login_url='login'), name='dispatch')
class DashboardView(View):
    def get(self, request):
        doctor = InnerMember.objects.get(user=request.user)

        appointments = Appointment.objects.filter(doctor=doctor)

        today = timezone.localdate()

        # today appointments
        today_appointments = appointments.filter(appointment_date=today)

        # upcoming
        upcoming_appointments = appointments.filter(
            appointment_date__gt=today
        ).order_by("appointment_date", "time_slot")

        # Completed
        completed = appointments.filter(
            status="completed"
        ).order_by("-appointment_date")

        # 🔹 Pending (today but not started)
        pending = today_appointments.filter(
            status="pending"
        ).order_by("time_slot")

        context = {
            "today_appointments": today_appointments,
            "upcoming_appointments": upcoming_appointments,
            "completed": completed,
            "pending": pending,
            "total": today_appointments.count(),
            "remaining_today": today_appointments.filter(
                status__in=["pending"]
            ).count(),
            
        }

        return render(request, "doctor/dashboard.html", context)


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
def billing(request):
     return render(request, 'doctor/billing.html')



@never_cache
@role_required('doctor')
def manage_patients(request):
    patients = Patient.objects.all().order_by('user__first_name')
    return render(request, 'doctor/manage_patients.html', {'patients': patients})


@never_cache
@role_required('doctor')
def view_patient(request, patient_id):
    patient = get_object_or_404(Patient, pk=patient_id)
    return render(request, 'doctor/view_patient.html', {'patient': patient})



@never_cache
@role_required('doctor')
def edit_patient(request, patient_id):
    patient = get_object_or_404(Patient, pk=patient_id)

    if request.method == 'POST':
        name = request.POST.get('name')
        email = request.POST.get('email')
        dob = request.POST.get('dob')
        gender = request.POST.get('gender')
        phone = request.POST.get('phone')
        bld_grop = request.POST.get('bld_grop')
        address = request.POST.get('address')

        if email and User.objects.filter(email=email).exclude(pk=patient.user.pk).exists():
            messages.error(request, 'Another user with this email already exists.')
            return render(request, 'doctor/edit_patient.html', {'patient': patient})

        patient.user.first_name = name or patient.user.first_name
        patient.user.email = email or patient.user.email
        patient.user.username = email or patient.user.username
        patient.user.save()

        patient.phone = phone
        patient.address = address
        patient.dob = dob if dob else None
        patient.gender = gender
        patient.bld_grop = bld_grop
        patient.save()

        messages.success(request, 'Patient updated successfully.')
        return redirect('doctor:manage_patients')

    return render(request, 'doctor/edit_patient.html', {'patient': patient})


@never_cache
@role_required('doctor')
def delete_patient(request, patient_id):
    patient = get_object_or_404(Patient, pk=patient_id)

    if request.method == 'POST':
        patient.user.delete()
        messages.success(request, 'Patient deleted successfully.')

    return redirect('doctor:manage_patients')


@never_cache
@role_required('doctor')
def add_patient(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        email = request.POST.get('email')
        dob = request.POST.get('dob')
        gender = request.POST.get('gender')
        phone = request.POST.get('phone')
        bld_grop = request.POST.get('bld_grop')
        address = request.POST.get('address')

        if User.objects.filter(email=email).exists():
            messages.error(request, 'A user with this email already exists.')
            return render(request, 'doctor/add_patient.html')

        # Split name into first and last name
        name_parts = name.strip().split(' ', 1)
        first_name = name_parts[0]
        last_name = name_parts[1] if len(name_parts) > 1 else ''

        try:
            with transaction.atomic():
                user = User.objects.create_user(
                    username=email, 
                    email=email, 
                    first_name=first_name, 
                    last_name=last_name, 
                    
                )

                Patient.objects.create(
                    user=user,
                    phone=phone,
                    address=address,
                    dob=dob if dob else None,
                    gender=gender,
                    bld_grop=bld_grop,
                )
            
            messages.success(request, 'Patient added successfully.')
            return redirect('doctor:manage_patients')
            
        except Exception as e:
            messages.error(request, f'An error occurred: {str(e)}')
            return render(request, 'doctor/add_patient.html')

    return render(request, 'doctor/add_patient.html')
