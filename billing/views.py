from django.shortcuts import render, redirect, get_object_or_404
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from django.contrib import messages
from decimal import Decimal
from .models import Bill, BillItem
from appointment.models import Visit, Appointment, Prescription, PrescriptionItem
from django.contrib.auth.models import User
from accounts.models import Patient, FamilyMember
from doctor.models import InnerMember
from appointment.models import Prescription
from clinic.models import ClinicSettings
from doctor.mixins import BillingAccessMixin
from django.utils import timezone
from django.utils.dateparse import parse_date


def get_bill_summary(visit):
    """
    Visit के सभी bills का summary - original + addon bills
    Returns payment tracking information
    """
    
    # Original bill
    original_bill = Bill.objects.filter(visit=visit, is_addon=False, is_archived=False).first()
    addon_bills = Bill.objects.filter(visit=visit, is_addon=True, is_archived=False)
    
    summary = {
        'original_bill': original_bill,
        'addon_bills': list(addon_bills),
        'original_total': original_bill.total if original_bill else Decimal('0'),
        'addon_total': sum(b.total for b in addon_bills),
        'grand_total': Decimal('0'),
        'original_paid': original_bill.total if (original_bill and original_bill.payment_status == 'paid') else Decimal('0'),
        'addon_paid': sum(b.total for b in addon_bills if b.payment_status == 'paid'),
        'total_paid': Decimal('0'),
        'pending_amount': Decimal('0'),
    }
    
    summary['grand_total'] = summary['original_total'] + summary['addon_total']
    summary['total_paid'] = summary['original_paid'] + summary['addon_paid']
    summary['pending_amount'] = summary['grand_total'] - summary['total_paid']
    
    return summary

def generate_bill_from_visit(visit):
    """
    Visit complete होने पर automatically bill बनाओ
    Prescription items से BillItems create करो
    
    Addon bills भी create करेगा अगर नई medicines add हों
    """
    from django.utils import timezone
    
    prescription = getattr(visit, 'prescription', None)

    if not prescription:
        return None

    # सभी items जो अभी तक billed नहीं हुई हैं
    new_items = prescription.items.select_related(
        'medicine_variant__medicine'
    ).filter(billed_on__isnull=True)

    # Check करो - क्या पहले से कोई bill है
    existing_bill = Bill.objects.filter(visit=visit, is_addon=False, is_archived=False).first()
    
    clinic = ClinicSettings.get()
    subtotal = Decimal('0')

    # Determine consultation fee based on appointment consultation_type if available
    consultation_fee = clinic.default_consultation_fee
    appt = getattr(visit, 'appointment', None)
    appt_type = getattr(appt, 'consultation_type', None)
    if appt_type == 'phone':
        consultation_fee = getattr(clinic, 'phone_consultation_fee', clinic.default_consultation_fee)
    elif appt_type == 'video':
        consultation_fee = getattr(clinic, 'video_consultation_fee', clinic.default_consultation_fee)

    if not new_items.exists():
        if not existing_bill:
            # Original bill बनाओ (सिर्फ consultation fee)
            bill = Bill.objects.create(
                visit=visit,
                subtotal=0,
                gst_percent=clinic.default_gst,
                consultation_fee=consultation_fee,
                is_addon=False
            )
            return bill
        else:
            return visit.bills.filter(is_archived=False).order_by('-created_at').first()

    if existing_bill:
        # Addon bill बनाओ
        bill = Bill.objects.create(
            visit=visit,
            subtotal=0,
            gst_percent=clinic.default_gst,
            consultation_fee=0,  # Addon में consultation fee नहीं
            is_addon=True,
            parent_bill=existing_bill,
            notes="Prescription amendment/addon"
        )
    else:
        # Original bill बनाओ
        bill = Bill.objects.create(
            visit=visit,
            subtotal=0,
            gst_percent=clinic.default_gst,
            consultation_fee=consultation_fee,
            is_addon=False
        )

    for item in new_items:
        variant = item.medicine_variant

        if not variant:
            continue

        try:
            parts = item.dosage.split(' (')
            dose_parts = [int(part) for part in parts[0].split('-')]
        except Exception:
            dose_parts = []

        qty = sum(dose_parts) * item.days

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
        
        # Item को mark करो - यह bill में add हो गई
        item.billed_on = timezone.now()
        item.bill_id = bill.id
        item.save()

    bill.subtotal = subtotal
    bill.save()

    return bill

@method_decorator(never_cache, name='dispatch')
class BillDetailView(LoginRequiredMixin,BillingAccessMixin, View):
    login_url = 'doctor:login'

    def get(self, request, hid):
        # Prefer numeric IDs when path segment is digits, else decode hashid
        from doctor import hashid as _hashid
        try:
            if isinstance(hid, str) and hid.isdigit():
                vid = int(hid)
            else:
                vid = _hashid.decode_hash(hid)
        except Exception:
            return get_object_or_404(Visit, id=0)

        visit = get_object_or_404(Visit, id=vid)

        # Bill generate करो (ताकि कोई pending items हों तो उनका bill बन जाए)
        latest_bill = generate_bill_from_visit(visit)

        bill_id = request.GET.get('bill_id')
        if bill_id:
            # bill_id may be a hashid or numeric id; prefer numeric when digits
            try:
                if bill_id.isdigit():
                    bid = int(bill_id)
                else:
                    bid = _hashid.decode_hash(bill_id)
            except Exception:
                bid = None

            if bid is None:
                bill = None
            else:
                bill = get_object_or_404(Bill, id=bid, visit=visit, is_archived=False)
        else:
            bill = latest_bill

        if not bill:
            # अगर कोई बिल नहीं है तो original bill check करो
            bill = Bill.objects.filter(visit=visit, is_addon=False, is_archived=False).first()
            if not bill:
                messages.error(request, 'No prescription found for this visit!')
                return redirect('appointment:manage_appointments')

        # Bill summary - सभी bills के साथ
        bill_summary = get_bill_summary(visit)

        return render(request, 'billing/bill_detail.html', {
            'bill': bill,
            'visit': visit,
            'bill_summary': bill_summary,
        })

    def post(self, request, hid):
        # Prefer numeric IDs when path segment is digits, else decode hashid
        from doctor import hashid as _hashid
        try:
            if isinstance(hid, str) and hid.isdigit():
                vid = int(hid)
            else:
                vid = _hashid.decode_hash(hid)
        except Exception:
            return get_object_or_404(Visit, id=0)

        visit = get_object_or_404(Visit, id=vid)

        bill_id = request.POST.get('bill_id')
        if bill_id:
            try:
                if bill_id.isdigit():
                    bid = int(bill_id)
                else:
                    bid = _hashid.decode_hash(bill_id)
            except Exception:
                bid = None

            if bid is None:
                bill = None
            else:
                bill = get_object_or_404(Bill, id=bid, visit=visit, is_archived=False)
        else:
            bill = Bill.objects.filter(visit=visit, is_addon=False, is_archived=False).first()

        # Update fields
        bill.gst_percent    = Decimal(request.POST.get('gst_percent', 18))
        bill.consultation_fee = Decimal(request.POST.get('consultation_fee', 0))
        bill.discount       = Decimal(request.POST.get('discount', 0))
        bill.payment_method = request.POST.get('payment_method', 'cash')
        bill.payment_status = request.POST.get('payment_status', 'unpaid')
        bill.notes          = request.POST.get('notes', '')
        bill.subtotal       = bill.subtotal  # same rakho
        bill.save()  # GST + total auto calculate hoga

        # Redirect back to bill detail using encoded hid
        from doctor import hashid as _hashid
        return redirect('billing:bill_detail', hid=_hashid.encode_id(visit.id))


@method_decorator(never_cache, name='dispatch')
class BillListView(LoginRequiredMixin, BillingAccessMixin, View):
    login_url = 'doctor:login'

    def get(self, request):
        
        search         = request.GET.get('search', '')
        bill_date      = request.GET.get('bill_date', '')
        selected_month = request.GET.get('bill_month', '')
        payment_status = request.GET.get('payment_status', 'all')

        bills = Bill.objects.select_related(
            'visit__patient__user'
        ).filter(is_archived=False).order_by('-created_at')

        # Global stats (not affected by search/filters)
        now = timezone.now()
        all_bills = Bill.objects.filter(is_archived=False)
        total_bills_count = all_bills.count()
        this_month_count = all_bills.filter(created_at__year=now.year, created_at__month=now.month).count()
        total_unpaid = all_bills.filter(payment_status='unpaid').count()
        total_partial = all_bills.filter(payment_status='partial').count()
        bill_months = all_bills.dates('bill_date', 'month', order='DESC')

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

        # Month filter
        if selected_month:
            month_date = parse_date(f'{selected_month}-01')
            if month_date:
                bills = bills.filter(
                    bill_date__year=month_date.year,
                    bill_date__month=month_date.month
                )

        # Status filter
        if payment_status and payment_status != 'all':
            bills = bills.filter(payment_status=payment_status)

        # Month-wise pagination logic
        from django.core.paginator import Paginator
        from django.db.models import Sum

        filtered_months = bills.dates('bill_date', 'month', order='DESC')
        
        month_paginator = Paginator(filtered_months, 4)
        month_page_number = request.GET.get('page', 1)
        month_page_obj = month_paginator.get_page(month_page_number)

        month_data = []
        for m_date in month_page_obj:
            month_bills = bills.filter(
                bill_date__year=m_date.year, 
                bill_date__month=m_date.month
            ).order_by('-created_at')

            totals = month_bills.aggregate(
                total_sum=Sum('total'),
            )
            total_sum = totals.get('total_sum') or 0
            
            paid_sum = month_bills.filter(payment_status='paid').aggregate(t=Sum('total'))['t'] or 0
            unpaid_sum = month_bills.filter(payment_status='unpaid').aggregate(t=Sum('total'))['t'] or 0

            page_param_name = f"page_{m_date.strftime('%Y_%m')}"
            inner_page_number = request.GET.get(page_param_name, 1)
            inner_paginator = Paginator(month_bills, 5)
            inner_page_obj = inner_paginator.get_page(inner_page_number)

            month_data.append({
                'month_date': m_date,
                'month_name': m_date.strftime('%B %Y'),
                'total_amount': total_sum,
                'paid_amount': paid_sum,
                'unpaid_amount': unpaid_sum,
                'bills': inner_page_obj,
                'page_param': page_param_name,
            })

        context_data = {
            'month_data':     month_data,
            'page_obj':       month_page_obj,
            'search':         search,
            'bill_date':      bill_date,
            'selected_month': selected_month,
            'bill_months':    bill_months,
            'payment_status': payment_status,
            'total_bills_count': total_bills_count,
            'this_month_count': this_month_count,
            'total_unpaid': total_unpaid,
            'total_partial': total_partial,
        }

        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return render(request, 'billing/bill_list.html', context_data)

        doctors = InnerMember.objects.filter(role='doctor').select_related('user')
        context_data['doctors'] = doctors

        return render(request, 'billing/bill_list.html', context_data)


@method_decorator(never_cache, name='dispatch')
class AddBillView(LoginRequiredMixin, BillingAccessMixin, View):
    login_url = 'doctor:login'

    def post(self, request):
        # Only collect minimal info: name, phone, appointment_date, appointment_time
        name = (request.POST.get('name') or '').strip()
        phone = (request.POST.get('phone') or '').strip()
        appointment_date = request.POST.get('appointment_date')
        appointment_time = request.POST.get('appointment_time')
        patient_id = request.POST.get('patient_id')
        family_member_id = request.POST.get('family_member_id')

        if not name or not phone or not appointment_date or not appointment_time:
            messages.error(request, 'Name, phone, appointment date and time are required.')
            return redirect('billing:bill_list')

        # Resolve selected patient / family member (if chosen from suggestions)
        patient = None
        family_member = None
        if family_member_id:
            try:
                family_member = FamilyMember.objects.get(id=family_member_id)
                patient = family_member.patient
            except FamilyMember.DoesNotExist:
                family_member = None

        if not patient and patient_id:
            try:
                patient = Patient.objects.get(id=patient_id)
            except Patient.DoesNotExist:
                patient = None

        # If still no patient found, fallback to lookup by phone or create new
        if not patient:
            patient = Patient.objects.filter(phone=phone).first()

        if not patient:
            # create new User
            username = phone or (name.replace(' ', '')[:30] or f'user{int(timezone.now().timestamp())}')
            if User.objects.filter(username=username).exists():
                username = f"{username}{int(timezone.now().timestamp())}"

            parts = name.split()
            first_name = parts[0] if parts else ''
            last_name = ' '.join(parts[1:]) if len(parts) > 1 else ''

            user = User.objects.create_user(username=username, password='password@123', first_name=first_name, last_name=last_name)
            try:
                patient = user.patient
                patient.phone = phone
                patient.save()
            except Exception:
                patient = Patient.objects.create(user=user, phone=phone)

        # parse appointment date/time
        appt_date_val = timezone.localdate()
        appt_time_val = timezone.localtime().time()
        try:
            appt_date_val = timezone.datetime.strptime(appointment_date, '%Y-%m-%d').date()
            appt_time_val = timezone.datetime.strptime(appointment_time, '%H:%M').time()
        except Exception:
            pass

        # create appointment and visit
        consultation_type = request.POST.get('consultation_type', 'in_person')
        appointment = Appointment.objects.create(
            patient=patient,
            appointment_date=appt_date_val,
            time_slot=appt_time_val,
            status='pending',
            consultation_type=consultation_type,
            family_member=family_member
        )

        visit = Visit.objects.create(
            patient=patient,
            doctor=None,
            appointment=appointment,
            visted_status='in_progress'
        )

        # redirect to prescription page to allow doctor to add prescription and then generate bill
        from django.urls import reverse
        return redirect(reverse('appointment:prescription', args=[visit.id]))

@method_decorator(never_cache, name='dispatch')
class DeleteBillView(LoginRequiredMixin, BillingAccessMixin, View):
    login_url = 'doctor:login'
    
    def post(self, request, hid):
        # Accept numeric id or hashid for bill
        from doctor import hashid as _hashid
        try:
            if isinstance(bill_id, str) and bill_id.isdigit():
                bid = int(bill_id)
            else:
                bid = _hashid.decode_hash(bill_id)
        except Exception:
            bid = None

        bill = get_object_or_404(Bill, id=bid, is_archived=False)
        bill_number = bill.bill_number
        
        appointment = None
        if bill.visit and bill.visit.appointment:
            appointment = bill.visit.appointment
            
        bill.delete()
        if appointment:
            appointment.delete()
            
        messages.success(request, f'Bill {bill_number} and its associated appointment deleted successfully.')
        return redirect('billing:bill_list')

@method_decorator(never_cache, name='dispatch')
class PrintBillView(LoginRequiredMixin,BillingAccessMixin,View):
    login_url = 'doctor:login'

    def get(self, request, hid):
        # Visit + Bill fetch karo. Accept numeric or hashid for visit and bill_id.
        from doctor import hashid as _hashid
        try:
            if isinstance(visit_id, str) and visit_id.isdigit():
                vid = int(visit_id)
            else:
                vid = _hashid.decode_hash(visit_id)
        except Exception:
            return get_object_or_404(Visit, id=0)

        visit = get_object_or_404(Visit, id=vid)
        bill_id = request.GET.get('bill_id')
        if bill_id:
            try:
                if bill_id.isdigit():
                    bid = int(bill_id)
                else:
                    bid = _hashid.decode_hash(bill_id)
            except Exception:
                bid = None

            if bid is None:
                bill = None
            else:
                bill = get_object_or_404(Bill, id=bid, visit=visit, is_archived=False)
        else:
            bill = Bill.objects.filter(visit=visit, is_addon=False, is_archived=False).first()

        # Clinic settings is a singleton managed by the clinic app.
        settings = ClinicSettings.get()

        return render(request, 'billing/bill_print.html', {
            'bill': bill,
            'visit': visit,
            'clinic': settings,
            'settings': settings,
        })
