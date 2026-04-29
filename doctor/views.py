from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.views.decorators.cache import never_cache
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from .decorators import role_required
from .models import InnerMember, Medicine
# Create your views here.

from django.contrib.auth import authenticate, login
from django.shortcuts import render, redirect, get_object_or_404
from .models import InnerMember, Medicine

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