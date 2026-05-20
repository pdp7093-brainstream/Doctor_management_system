from django.shortcuts import render, redirect, get_object_or_404
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from django.contrib import messages
from decimal import Decimal
from .models import Bill, BillItem
from appointment.models import Visit
from clinic.models import ClinicSettings
from doctor.mixins import BillingAccessMixin

def generate_bill_from_visit(visit):
    """
    Visit complete hone ke baad automatically bill banao
    Prescription items se BillItems create karo
    """

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

        variant = item.medicine_variant

        if not variant:
            continue

        try:
            parts = item.dosage.split(' (')
            m_a_n = parts[0].split('-')

            m = int(m_a_n[0])
            a = int(m_a_n[1])
            n = int(m_a_n[2])

        except Exception:
            m = a = n = 0

        qty = (m + a + n) * item.days

        unit_price = variant.selling_price

        total = qty * unit_price

        BillItem.objects.create(
            bill=bill,
            medicine_variant=variant,
            medicine_name=variant.medicine.name,
            power=variant.power,
            quantity=qty,
            unit_price=unit_price,
            total_price=total,
        )

        subtotal += total

    bill.subtotal = subtotal
    bill.save()

    return bill

@method_decorator(never_cache, name='dispatch')
class BillDetailView(LoginRequiredMixin,BillingAccessMixin, View):
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

        return redirect('billing:bill_detail', visit_id=visit_id)


@method_decorator(never_cache, name='dispatch')
class BillListView(LoginRequiredMixin, BillingAccessMixin, View):
    login_url = 'doctor:login'

    def get(self, request):
        search         = request.GET.get('search', '')
        bill_date      = request.GET.get('bill_date', '')
        payment_status = request.GET.get('payment_status', 'all')

        bills = Bill.objects.select_related(
            'visit__patient__user'
        ).order_by('-created_at')

        # Search — patient name ya bill number
        if search:
            from django.db.models import Q
            bills = bills.filter(
                Q(bill_number__icontains=search) |
                Q(visit__patient__user__first_name__icontains=search) |
                Q(visit__patient__user__last_name__icontains=search)
            )

        # Date filter
        if bill_date:
            bills = bills.filter(bill_date=bill_date)

        # Status filter
        if payment_status and payment_status != 'all':
            bills = bills.filter(payment_status=payment_status)

        # Pagination — 20 per page
        from django.core.paginator import Paginator
        paginator   = Paginator(bills, 20)
        page_number = request.GET.get('page', 1)
        page_obj    = paginator.get_page(page_number)

        unpaid_count = bills.filter(payment_status='unpaid').count()
        partial_count = bills.filter(payment_status='partial').count()
        
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return render(request, 'billing/bill_list.html', {
                'bills':          page_obj,
                'page_obj':       page_obj,
                'search':         search,
                'bill_date':      bill_date,
                'payment_status': payment_status,
            })

        return render(request, 'billing/bill_list.html', {
            'bills':          page_obj,
            'page_obj':       page_obj,
            'search':         search,
            'bill_date':      bill_date,
            'payment_status': payment_status,
            'unpaid_count':   unpaid_count,
            'partial_count':  partial_count,
        })

@method_decorator(never_cache, name='dispatch')
class PrintBillView(LoginRequiredMixin,BillingAccessMixin,View):
    login_url = 'doctor:login'

    def get(self, request, visit_id):
        # Visit + Bill fetch karo
        visit = get_object_or_404(Visit, id=visit_id)
        bill  = get_object_or_404(Bill, visit=visit)

        # Clinic settings is a singleton managed by the clinic app.
        settings = ClinicSettings.get()

        return render(request, 'billing/bill_print.html', {
            'bill': bill,
            'visit': visit,
            'clinic': settings,
            'settings': settings,
        })
