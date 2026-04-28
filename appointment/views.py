from django.shortcuts import render,redirect
from django.views import View
from doctor.decorators import role_required
from accounts.models import Patient
from doctor.models import InnerMember
from .models import Appointment
from django.views.decorators.cache import never_cache
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator

from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from datetime import datetime
# Create your views here.


@method_decorator([never_cache, role_required("doctor")], name="dispatch")
class Manage_appointments(View):
    def get(self, request):
        doctor = InnerMember.objects.get(user=request.user)
        appointments = Appointment.objects.filter(doctor=doctor).order_by(
            "-appointment_date"
        )
        context = {"appointments": appointments}
        return render(request, "doctor/manage_appointments.html", context)


@method_decorator([never_cache, role_required("doctor")], name="dispatch")
class Add_appointment(View):
    def get(self, request):
        
        return render(request, "doctor/add_appointment.html")

    
    

@login_required(login_url='login')
def appointment(request):
    return render(request, "appointment.html")
