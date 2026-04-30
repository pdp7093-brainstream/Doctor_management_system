from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.views.decorators.cache import never_cache
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from .decorators import role_required
from .models import InnerMember, Medicine
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


from django.utils.timezone import now
from appointment.models import Appointment
from .models import InnerMember


@never_cache
@role_required('doctor')
def dashboard(request):
    today = now().date()

    # 🔥 safe doctor fetch (error avoid karega)
    try:
        doctor = InnerMember.objects.get(user=request.user)
    except InnerMember.DoesNotExist:
        return render(request, 'doctor/dashboard.html', {
            'error': 'Doctor profile not found'
        })

    # 🔥 DEBUG (temporary laga ke check karo)
    print("LOGGED IN DOCTOR ID:", doctor.id)
    print("TODAY DATE:", today)

    # 🔥 appointments filter
    appointments = Appointment.objects.filter(
        doctor=doctor,
        appointment_date=today
    ).order_by('time_slot')

    # 🔥 DEBUG
    print("TOTAL FOUND:", appointments.count())

    # counts
    total_appointments = appointments.count()
    pending_appointments = appointments.filter(status='pending').count()
    confirmed_appointments = appointments.filter(status='confirmed').count()
    cancelled_appointments = appointments.filter(status='cancelled').count()

    context = {
        'total_appointments': total_appointments,
        'pending_appointments': pending_appointments,
        'confirmed_appointments': confirmed_appointments,
        'cancelled_appointments': cancelled_appointments,
        'appointments': appointments
    }

    return render(request, 'doctor/dashboard.html', context)

@never_cache
@login_required
def manage_patients(request):
     return render(request, 'doctor/manage_patients.html')


@never_cache    
@login_required
def add_patient(request):
     return render(request, 'doctor/add_patient.html')




class ManageMedicineView(LoginRequiredMixin, View):
    login_url = 'doctor:login'

    def get(self, request):
        medicines = Medicine.objects.all().order_by('-created_at')
        return render(request, 'doctor/manage_medicine.html', {'medicines': medicines})


class AddMedicineView(LoginRequiredMixin, View):
    login_url = 'doctor:login'

    def get(self, request):
        return render(request, 'doctor/add_medicine.html')

    def post(self, request):
        name = request.POST.get('name')
        stock = request.POST.get('stock')
        price = request.POST.get('price')
        mfg_date = request.POST.get('mfg_date')
        exp_date = request.POST.get('exp_date')

        Medicine.objects.create(
            name=name,
            stock=stock,
            price=price,
            mfg_date=mfg_date,
            expiry_date=exp_date,
        )
        return redirect('doctor:manage_medicine')


class DeleteMedicineView(LoginRequiredMixin, View):
    login_url = 'doctor:login'

    def post(self, request, pk):
        medicine = get_object_or_404(Medicine, pk=pk)
        medicine.delete()
        return redirect('doctor:manage_medicine')


class EditMedicineView(LoginRequiredMixin, View):
    login_url = 'doctor:login'

    def get(self, request, pk):
        medicine = get_object_or_404(Medicine, pk=pk)
        return render(request, 'doctor/edit_medicine.html', {'medicine': medicine})

    def post(self, request, pk):
        medicine = get_object_or_404(Medicine, pk=pk)
        medicine.name = request.POST.get('name')
        medicine.stock = request.POST.get('stock')
        medicine.price = request.POST.get('price')
        medicine.mfg_date = request.POST.get('mfg_date')
        medicine.expiry_date = request.POST.get('exp_date')
        medicine.save()
        return redirect('doctor:manage_medicine')

@never_cache
@login_required
def billing(request):
     return render(request, 'doctor/billing.html')



@never_cache
@role_required('doctor')
def manage_patients(request):
    patients = Patient.objects.select_related('user').all().order_by('user__first_name')
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

        user = User.objects.create_user(username=email, email=email, first_name=name, password='defaultpassword123')

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

    return render(request, 'doctor/add_patient.html')
