from django.shortcuts import render,redirect,get_object_or_404
from django.views import View
from doctor.decorators import role_required
from accounts.models import Patient
from doctor.models import InnerMember
from medicine.models import *
from .models import *
from django.views.decorators.cache import never_cache
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.utils import timezone
from django.http import JsonResponse
from django.contrib import messages
from django.db.models import Q, Value
from django.db.models.functions import Concat
from datetime import datetime,time, timedelta
# Create your views here.

# ------------ Slot generate start --------------
def generate_slots():
    start = time(9, 0)
    end = time(17, 0)
    interval = 30

    slots = []
    current = datetime.combine(datetime.today(), start)

    while current.time() < end:
        slots.append(current.time())
        current += timedelta(minutes=interval)

    return slots


def get_slots(request):
    date_str = request.GET.get('appointment_date')

    if not date_str:
        return JsonResponse({'error': 'Date required'})

    selected_date = datetime.strptime(date_str, "%Y-%m-%d").date()

    all_slots = generate_slots()

    booked = Appointment.objects.filter(
        appointment_date=selected_date
    ).values_list('time_slot', flat=True)

    booked = [t.strftime("%H:%M") for t in booked]

    now = timezone.localtime()
    current_time = now.time()

    filtered = []

    for slot in all_slots:
        slot_str = slot.strftime("%H:%M")

        # ✅ Past remove (FIXED)
        if selected_date == now.date() and slot <= current_time:
            continue

        # ✅ Booked remove
        if slot_str in booked:
            continue

        filtered.append(slot_str)

    return JsonResponse({'slots': filtered})
# ------------ Slot generate end  --------------
from django.utils.decorators import method_decorator
from django.views import View
from django.shortcuts import render
from django.db.models import Q
from django.views.decorators.cache import never_cache
from doctor.decorators import role_required
from .models import Appointment
from doctor.models import InnerMember
from django.core.paginator import Paginator



@method_decorator([never_cache, role_required("doctor")], name="dispatch")
class Manage_appointments(View):
    def get(self, request):
        doctor = InnerMember.objects.get(user=request.user)
        
        search = request.GET.get('search', '')
        appointment_date = request.GET.get('appointment_date', '')
        status = request.GET.get('status', 'all')

        appointments = Appointment.objects.filter(
            doctor=doctor
        ).order_by("-appointment_date", "-time_slot")

        # Search filter
        if search:
            appointments = appointments.filter(
                Q(patient__user__first_name__icontains=search) |
                Q(patient__user__last_name__icontains=search) |
                Q(patient__phone__icontains=search)
            )

        # Date filter
        if appointment_date:
            appointments = appointments.filter(appointment_date=appointment_date)

        # Status filter
        if status and status != 'all':
            appointments = appointments.filter(status=status)

        # Pagination — 20 per page
        paginator = Paginator(appointments, 20)
        page_number = request.GET.get('page', 1)
        page_obj = paginator.get_page(page_number)

        # AJAX request
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return render(request, 'doctor/manage_appointments.html', {
                'appointments': page_obj,
                'page_obj': page_obj,
                'search': search,
                'appointment_date': appointment_date,
                'status': status,
            })

        return render(request, 'doctor/manage_appointments.html', {
            'appointments': page_obj,
            'page_obj': page_obj,
            'search': search,
            'appointment_date': appointment_date,
            'status': status,
        })




@method_decorator([never_cache, role_required("doctor")], name="dispatch")
class Add_appointment(View):
    def get(self, request):
        record = Patient.objects.all()
        return render(request, "doctor/add_appointment.html",{"record":record})

    def post(slef,request):
        patient_id = request.POST.get("patient")
        appointment_date = request.POST.get("appointment_date")
        time_slot = request.POST.get("time_slot")
        notes = request.POST.get("notes")
        doctor = InnerMember.objects.get(user=request.user)
        patient = Patient.objects.get(id=patient_id)

        appointment = Appointment.objects.create(
            patient=patient,
            appointment_date=appointment_date,
            time_slot=time_slot,
            notes=notes,
            doctor=doctor
        )
        return redirect('appointment:manage_appointments')     
    

@method_decorator(login_required(login_url='login'), name='dispatch')
class Book_appointment(View):
    def get(self,request):
        return render(request, "appointment.html")

    def post(self, request):
        user = request.user
        appointment_date = request.POST.get("date")
        time_slot = request.POST.get("time_slot")
        notes = request.POST.get("message")

        # 🔥 convert 12hr → 24hr (IMPORTANT)
        from datetime import datetime
        time_24 = datetime.strptime(time_slot, "%I:%M %p").time()

        
        patient = Patient.objects.get(user=user)

        # doctor assign (simple for now)
        doctor = InnerMember.objects.first()

        # 🔥 DOUBLE BOOKING PREVENTION
        if Appointment.objects.filter(
            appointment_date=appointment_date,
            time_slot=time_24
        ).exists():
            messages.error(request, "This time slot is already booked. Please choose another.")
            return redirect('appointment:appointment')

        
        Appointment.objects.create(
            patient=patient,
            doctor=doctor,
            appointment_date=appointment_date,
            time_slot=time_24,
            notes=notes
        )

        messages.success(request, "Appointment booked successfully!")
        return redirect('appointment:appointment')

@method_decorator([never_cache, role_required("doctor")], name="dispatch")
class StartVisitView(View):
    def get(self,request,appointment_id):
        appointment = get_object_or_404(Appointment,id=appointment_id)

        visit, created = Visit.objects.get_or_create(
            appointment = appointment,
            defaults = {
                "patient":appointment.patient,
                "doctor":appointment.doctor,
                "visted_status":'in_progress'
            }
        )

        return redirect("appointment:prescription",visit_id=visit.id)

@method_decorator([never_cache, role_required("doctor")], name="dispatch")
class PrescriptionView(View):
    def get(self, request, visit_id):
        visit = get_object_or_404(Visit, id=visit_id)
        prescription, created = Prescription.objects.get_or_create(visit=visit)
        variants = MedicineVariant.objects.filter(medicine__is_active=True)
        items = prescription.items.select_related(
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
            'visit': visit,
            'variants': variants,
            'items': items
        })

    def reduce_stock(self, prescription):
        """
        Sirf un items ka stock minus karo jinka should_deduct = True hai.
        Complete hone ke baad should_deduct = False ho jaayega automatically.
        """
        errors = []

        pending_items = prescription.items.select_related(
            'medicine_variant__medicine'
        ).filter(should_deduct=True)

        for item in pending_items:
            variant = item.medicine_variant

            try:
                parts = item.dosage.split(' (')
                m_a_n = parts[0].split('-')
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
                variant.save()
            else:
                errors.append(
                    f"{variant.medicine.name} - {variant.power}: "
                    f"Required {total_qty}, Available {variant.stock}"
                )
                variant.stock = 0
                variant.save()

            # ✅ Stock minus ho gaya — toggle OFF, history ON
            item.should_deduct = False
            item.was_deducted  = True
            item.save()

        return errors

    def post(self, request, visit_id):
        visit = get_object_or_404(Visit, id=visit_id)

        visit.symptoms  = request.POST.get("symptoms")
        visit.diagnosis = request.POST.get("diagnosis")
        visit.notes     = request.POST.get("notes")

        is_completing = "complete_visit" in request.POST

        if is_completing:
            visit.visted_status = "completed"
        else:
            visit.visted_status = "in_progress"

        visit.save()

        prescription, created = Prescription.objects.get_or_create(visit=visit)

        variant_ids      = request.POST.getlist("variant_id[]")
        item_ids         = request.POST.getlist("item_id[]")
        morning_list     = request.POST.getlist("morning")
        afternoon_list   = request.POST.getlist("afternoon")
        night_list       = request.POST.getlist("night")
        meal_list        = request.POST.getlist("meal")
        days_list        = request.POST.getlist("days")
        # ✅ Toggle values — checked = "on", unchecked = missing
        deduct_list      = request.POST.getlist("should_deduct[]")

        existing_item_ids  = list(prescription.items.values_list('id', flat=True))
        submitted_item_ids = []

        for i, (item_id_str, v_id, m, a, n, meal, days) in enumerate(zip(
            item_ids, variant_ids,
            morning_list, afternoon_list, night_list,
            meal_list, days_list
        )):
            if not v_id:
                continue

            variant = MedicineVariant.objects.get(id=v_id)
            dosage  = f"{m}-{a}-{n} ({meal})"

            # ✅ Toggle: checkbox name = "should_deduct[]" with value = index
            should_deduct = str(i) in deduct_list

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
                    item.should_deduct    = should_deduct  # ✅ Toggle save
                    item.save()
                except PrescriptionItem.DoesNotExist:
                    pass
            else:
                new_item = PrescriptionItem.objects.create(
                    prescription     = prescription,
                    medicine_variant = variant,
                    dosage           = dosage,
                    days             = int(days),
                    should_deduct    = should_deduct,  # ✅ Toggle save
                    was_deducted     = False,
                )
                submitted_item_ids.append(new_item.id)

        # Delete removed items
        items_to_delete = set(existing_item_ids) - set(submitted_item_ids)
        if items_to_delete:
            PrescriptionItem.objects.filter(id__in=items_to_delete).delete()

        # ✅ Stock minus — sirf complete_visit pe
        if is_completing:
            stock_errors = self.reduce_stock(prescription)
            if stock_errors:
                for err in stock_errors:
                    messages.warning(request, f"Low stock: {err}")

        appointment = visit.appointment
        appointment.status = "completed" if is_completing else "confirmed"
        appointment.save()

        return redirect("appointment:manage_appointments")