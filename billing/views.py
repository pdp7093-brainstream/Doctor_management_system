from django.shortcuts import render, redirect, get_object_or_404
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from django.http import HttpResponse
from django.template.loader import render_to_string
from django.contrib import messages
from decimal import Decimal
from .models import Bill, BillItem
from appointment.models import Visit, PrescriptionItem


def generate_bill_from_visit(visit):
    """
    Visit complete hone ke baad automatically bill banao
    Prescription items se BillItems create karo
    """
    # Lazy import to avoid circular import (appointment → billing → clinic)
    from clinic.models import ClinicSettings

    # Agar bill already hai to return karo
    if hasattr(visit, 'bill'):
        return visit.bill

    prescription = getattr(visit, 'prescription', None)
    if not prescription:
        return None

    items = prescription.items.select_related(
        'medicine_variant__medicine'
    )

    subtotal = Decimal('0')

    clinic = ClinicSettings.get()
    
    bill = Bill.objects.create(
        visit=visit,
        subtotal=0,
        gst_percent=clinic.default_gst,
        consultation_fee=clinic.default_consultation_fee,
    )

    for item in items:
        variant   = item.medicine_variant
        if not variant:
            continue

        # Qty calculate karo dosage se
        try:
            parts = item.dosage.split(' (')
            m_a_n = parts[0].split('-')
            m = int(m_a_n[0])
            a = int(m_a_n[1])
            n = int(m_a_n[2])
        except Exception:
            m = a = n = 0

        qty        = (m + a + n) * item.days
        unit_price = variant.selling_price
        total      = qty * unit_price

        BillItem.objects.create(
            bill             = bill,
            medicine_variant = variant,
            medicine_name    = variant.medicine.name,
            power            = variant.power,
            quantity         = qty,
            unit_price       = unit_price,
            total_price      = total,
        )

        subtotal += total

    # Bill update karo
    bill.subtotal = subtotal
    bill.save()

    return bill


@method_decorator(never_cache, name='dispatch')
class BillDetailView(LoginRequiredMixin, View):
    login_url = 'doctor:login'

    def get(self, request, visit_id):
        visit = get_object_or_404(Visit, id=visit_id)

        # Bill nahi hai to banao
        if not hasattr(visit, 'bill'):
            bill = generate_bill_from_visit(visit)
        else:
            bill = visit.bill

        if not bill:
            messages.error(request, 'No prescription found for this visit!')
            return redirect('appointment:manage_appointments')

        return render(request, 'billing/bill_detail.html', {
            'bill': bill,
            'visit': visit,
        })

    def post(self, request, visit_id):
        visit = get_object_or_404(Visit, id=visit_id)
        bill  = get_object_or_404(Bill, visit=visit)

        # Update fields
        bill.gst_percent    = Decimal(request.POST.get('gst_percent', 18))
        bill.consultation_fee = Decimal(request.POST.get('consultation_fee', 0))
        bill.discount       = Decimal(request.POST.get('discount', 0))
        bill.payment_method = request.POST.get('payment_method', 'cash')
        bill.payment_status = request.POST.get('payment_status', 'unpaid')
        bill.notes          = request.POST.get('notes', '')
        bill.subtotal       = bill.subtotal  # same rakho
        bill.save()  # GST + total auto calculate hoga

        messages.success(request, 'Bill updated successfully!')
        return redirect('billing:bill_detail', visit_id=visit_id)


@method_decorator(never_cache, name='dispatch')
class BillListView(LoginRequiredMixin, View):
    login_url = 'doctor:login'

    def get(self, request):
        from doctor.models import InnerMember
        doctor = InnerMember.objects.get(user=request.user)

        bills = Bill.objects.filter(
            visit__doctor=doctor
        ).select_related(
            'visit__patient__user'
        ).order_by('-created_at')

        return render(request, 'billing/bill_list.html', {'bills': bills})


from django.shortcuts import render, get_object_or_404
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache

from appointment.models import Visit
from .models import Bill
from doctor.models import ClinicSettings


@method_decorator(never_cache, name='dispatch')
class PrintBillView(LoginRequiredMixin, View):
    login_url = 'doctor:login'

    def get(self, request, visit_id):
        # Visit + Bill fetch karo
        visit = get_object_or_404(Visit, id=visit_id)
        bill  = get_object_or_404(Bill, visit=visit)

        # Clinic settings fetch karo (safe way)
        settings = ClinicSettings.objects.filter(
            doctor=visit.doctor
        ).first()

        return render(request, 'billing/bill_print.html', {
            'bill': bill,
            'visit': visit,
            'settings': settings   
        })