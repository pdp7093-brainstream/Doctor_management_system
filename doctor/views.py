from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.views.decorators.cache import never_cache
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from .decorators import role_required
from .models import InnerMember
from medicine.models import Medicine, MedicineVariant
from appointment.models import Appointment
from django.utils import timezone
from django.utils.decorators import method_decorator





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




# @method_decorator([never_cache, role_required("doctor")], name="dispatch")
# class Manage_appointments(View):
#     def get(self, request):
#         doctor = InnerMember.objects.get(user=request.user)
#         appointments = Appointment.objects.filter(doctor=doctor).order_by(
#             "-appointment_date"
#         )
#         context = {"appointments": appointments}
#         return render(request, "doctor/manage_appointments.html", context)




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