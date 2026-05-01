from medicine.models import *
from .models import *
from django.shortcuts import render, redirect, get_object_or_404
from django.views import View
from doctor.decorators import role_required
from accounts.models import Patient
from doctor.models import InnerMember
from django.views.decorators.cache import never_cache
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.utils import timezone
from django.http import JsonResponse
from django.contrib import messages
from django.db.models import Q
from django.core.paginator import Paginator
from datetime import datetime, time, timedelta


# ─────────────────────────────────────────
# Slot Generator
# ─────────────────────────────────────────

def generate_slots():
    start    = time(9, 0)
    end      = time(17, 0)
    interval = 30
    slots    = []
    current  = datetime.combine(datetime.today(), start)

    while current.time() < end:
        slots.append(current.time())
        current += timedelta(minutes=interval)

    return slots


def get_slots(request):
    date_str = request.GET.get('appointment_date')

    if not date_str:
        return JsonResponse({'error': 'Date required'})

    selected_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    all_slots     = generate_slots()

    booked = Appointment.objects.filter(
        appointment_date=selected_date
    ).values_list('time_slot', flat=True)
    booked = [t.strftime("%H:%M") for t in booked]

    now          = timezone.localtime()
    current_time = now.time()
    filtered     = []

    for slot in all_slots:
        slot_str = slot.strftime("%H:%M")

        # Remove past slots for today
        if selected_date == now.date() and slot <= current_time:
            continue

        # Remove already booked slots
        if slot_str in booked:
            continue

        filtered.append(slot_str)

    return JsonResponse({'slots': filtered})


# ─────────────────────────────────────────
# Manage Appointments (Doctor)
# ─────────────────────────────────────────

@method_decorator([never_cache, role_required("doctor")], name="dispatch")
class Manage_appointments(View):
    def get(self, request):
        doctor = InnerMember.objects.get(user=request.user)

        search           = request.GET.get('search', '')
        appointment_date = request.GET.get('appointment_date', '')
        status           = request.GET.get('status', 'all')

        # Show doctor's appointments + unassigned ones
        appointments = Appointment.objects.filter(
            Q(doctor=doctor) | Q(doctor__isnull=True)
        )

        if search:
            appointments = appointments.filter(
                Q(full_name__icontains=search) |
                Q(phone__icontains=search) |
                Q(patient__user__first_name__icontains=search) |
                Q(patient__user__last_name__icontains=search)
            )

        if appointment_date:
            appointments = appointments.filter(appointment_date=appointment_date)

        if status and status != 'all':
            appointments = appointments.filter(status=status)

        appointments = appointments.order_by('-appointment_date', '-time_slot')

        paginator  = Paginator(appointments, 10)
        page_obj   = paginator.get_page(request.GET.get('page'))

        context = {
            'appointments'    : page_obj,
            'page_obj'        : page_obj,
            'search'          : search,
            'appointment_date': appointment_date,
            'status'          : status,
        }

        # AJAX — return only table partial
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return render(request, 'doctor/partials/appointments_table.html', context)

        return render(request, 'doctor/manage_appointments.html', context)


# ─────────────────────────────────────────
# Add Appointment (Doctor)
# ─────────────────────────────────────────

@method_decorator([never_cache, role_required("doctor")], name="dispatch")
class Add_appointment(View):
    def get(self, request):
        record = Patient.objects.all()
        return render(request, "doctor/add_appointment.html", {"record": record})

    def post(self, request):
        patient_id       = request.POST.get("patient")
        appointment_date = request.POST.get("appointment_date")
        time_slot        = request.POST.get("time_slot")
        notes            = request.POST.get("notes")
        doctor           = InnerMember.objects.get(user=request.user)
        patient          = Patient.objects.get(id=patient_id)

        Appointment.objects.create(
            patient          = patient,
            doctor           = doctor,
            appointment_date = appointment_date,
            time_slot        = time_slot,
            notes            = notes,
        )
        return redirect('appointment:manage_appointments')


# ─────────────────────────────────────────
# Book Appointment (Patient)
# ─────────────────────────────────────────

@method_decorator(login_required(login_url='login'), name='dispatch')
class Book_appointment(View):
    def get(self, request):
        return render(request, "appointment.html")

    def post(self, request):
        name             = request.POST.get('name')
        appointment_date = request.POST.get("date")
        time_slot        = request.POST.get("time_slot")
        notes            = request.POST.get("message")

        # Convert 12hr → 24hr
        time_24 = datetime.strptime(time_slot, "%I:%M %p").time()

        patient = Patient.objects.get(user=request.user)
        doctor  = InnerMember.objects.first()   # simple assign — update logic later

        # Double booking prevention
        if Appointment.objects.filter(
            appointment_date=appointment_date,
            time_slot=time_24
        ).exists():
            messages.error(request, "This time slot is already booked. Please choose another.")
            return redirect('appointment:appointment')

        Appointment.objects.create(
            full_name        = name,
            patient          = patient,
            doctor           = doctor,
            appointment_date = appointment_date,
            time_slot        = time_24,
            notes            = notes,
        )

        messages.success(request, "Appointment booked successfully!")
        return redirect('appointment:appointment')


# ─────────────────────────────────────────
# Start Visit (Doctor)
# ─────────────────────────────────────────

@method_decorator([never_cache, role_required("doctor")], name="dispatch")
class StartVisitView(View):
    def get(self, request, appointment_id):
        appointment = get_object_or_404(Appointment, id=appointment_id)

        visit, created = Visit.objects.get_or_create(
            appointment=appointment,
            defaults={
                "patient"      : appointment.patient,
                "doctor"       : appointment.doctor,
                "visted_status": 'in_progress',
            }
        )

        return redirect("appointment:prescription", visit_id=visit.id)


# ─────────────────────────────────────────
# Prescription (Doctor)
# ─────────────────────────────────────────

@method_decorator([never_cache, role_required("doctor")], name="dispatch")
class PrescriptionView(View):
    def get(self, request, visit_id):
        visit        = get_object_or_404(Visit, id=visit_id)
        prescription, _ = Prescription.objects.get_or_create(visit=visit)
        variants     = MedicineVariant.objects.filter(medicine__is_active=True)
        items        = prescription.items.select_related(
            'medicine_variant', 'medicine_variant__medicine'
        )

        for item in items:
            try:
                parts = item.dosage.split(' (')
                m_a_n = parts[0].split('-')
                item.parsed_morning   = int(m_a_n[0])
                item.parsed_afternoon = int(m_a_n[1])
                item.parsed_night     = int(m_a_n[2])
                item.parsed_meal      = parts[1].replace(')', '')
            except Exception:
                item.parsed_morning   = 0
                item.parsed_afternoon = 0
                item.parsed_night     = 0
                item.parsed_meal      = 'after_food'

        return render(request, 'doctor/prescription.html', {
            'visit'   : visit,
            'variants': variants,
            'items'   : items,
        })

    def reduce_stock(self, prescription):
        """
        Sirf un items ka stock minus karo jinka should_deduct=True ho.
        Complete hone ke baad should_deduct=False ho jaata hai.
        """
        errors        = []
        pending_items = prescription.items.select_related(
            'medicine_variant__medicine'
        ).filter(should_deduct=True)

        for item in pending_items:
            variant = item.medicine_variant

            try:
                parts     = item.dosage.split(' (')
                m_a_n     = parts[0].split('-')
                morning   = int(m_a_n[0])
                afternoon = int(m_a_n[1])
                night     = int(m_a_n[2])
            except Exception:
                morning = afternoon = night = 0

            total_qty = (morning + afternoon + night) * item.days

            if total_qty <= 0:
                item.should_deduct = False
                item.was_deducted  = True
                item.save()
                continue

            if variant.stock >= total_qty:
                variant.stock -= total_qty
            else:
                errors.append(
                    f"{variant.medicine.name} - {variant.power}: "
                    f"Required {total_qty}, Available {variant.stock}"
                )
                variant.stock = 0

            variant.save()
            item.should_deduct = False
            item.was_deducted  = True
            item.save()

        return errors

    def post(self, request, visit_id):
        visit = get_object_or_404(Visit, id=visit_id)

        visit.symptoms  = request.POST.get("symptoms")
        visit.diagnosis = request.POST.get("diagnosis")
        visit.notes     = request.POST.get("notes")

        is_completing       = "complete_visit" in request.POST
        visit.visted_status = "completed" if is_completing else "in_progress"
        visit.save()

        prescription, _ = Prescription.objects.get_or_create(visit=visit)

        variant_ids    = request.POST.getlist("variant_id[]")
        item_ids       = request.POST.getlist("item_id[]")
        morning_list   = request.POST.getlist("morning")
        afternoon_list = request.POST.getlist("afternoon")
        night_list     = request.POST.getlist("night")
        meal_list      = request.POST.getlist("meal")
        days_list      = request.POST.getlist("days")
        deduct_list    = request.POST.getlist("should_deduct[]")  # checkbox indices

        existing_item_ids  = list(prescription.items.values_list('id', flat=True))
        submitted_item_ids = []

        for i, (item_id_str, v_id, m, a, n, meal, days) in enumerate(zip(
            item_ids, variant_ids,
            morning_list, afternoon_list, night_list,
            meal_list, days_list
        )):
            if not v_id:
                continue

            variant       = MedicineVariant.objects.get(id=v_id)
            dosage        = f"{m}-{a}-{n} ({meal})"
            should_deduct = str(i) in deduct_list   # checkbox toggle

            if item_id_str:
                try:
                    item_id_int = int(item_id_str)
                    submitted_item_ids.append(item_id_int)
                    item = PrescriptionItem.objects.get(
                        id=item_id_int, prescription=prescription
                    )
                    item.medicine_variant = variant
                    item.dosage           = dosage
                    item.days             = int(days)
                    item.should_deduct    = should_deduct
                    item.save()
                except PrescriptionItem.DoesNotExist:
                    pass
            else:
                new_item = PrescriptionItem.objects.create(
                    prescription     = prescription,
                    medicine_variant = variant,
                    dosage           = dosage,
                    days             = int(days),
                    should_deduct    = should_deduct,
                    was_deducted     = False,
                )
                submitted_item_ids.append(new_item.id)

        # Delete removed items
        items_to_delete = set(existing_item_ids) - set(submitted_item_ids)
        if items_to_delete:
            PrescriptionItem.objects.filter(id__in=items_to_delete).delete()

        # Reduce stock only on complete_visit
        if is_completing:
            stock_errors = self.reduce_stock(prescription)
            for err in stock_errors:
                messages.warning(request, f"Low stock: {err}")

        appointment        = visit.appointment
        appointment.status = "completed" if is_completing else "confirmed"
        appointment.save()

        return redirect("appointment:manage_appointments")


# ─────────────────────────────────────────
# Appointment Detail (Patient)
# ─────────────────────────────────────────

@login_required(login_url='login')
def appointment_detail(request, id):
    appointment = get_object_or_404(Appointment, id=id, patient=request.user.patient)

    visit             = Visit.objects.filter(appointment=appointment).first()
    prescription      = None
    prescription_items = []

    if visit:
        prescription = Prescription.objects.filter(visit=visit).first()
        if prescription:
            prescription_items = prescription.items.select_related(
                'medicine_variant',
                'medicine_variant__medicine'
            ).all()

    return render(request, 'pdashboard/appointment_details.html', {
        'appointment'       : appointment,
        'visit'             : visit,
        'prescription'      : prescription,
        'prescription_items': prescription_items,
    })