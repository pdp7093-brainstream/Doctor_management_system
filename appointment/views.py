from medicine.models import *
from .models import *
from django.shortcuts import render, redirect, get_object_or_404
from django.template.loader import render_to_string
from django.views import View
from doctor.decorators import role_required
from accounts.models import Patient, FamilyMember  # ← MAKE SURE THIS IS HERE
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
from billing.views import generate_bill_from_visit
from clinic.models import ClinicSettings
import json
import re


def resolve_hid(hid):
    """Resolve a path id that may be a numeric string or a hashid.
    Prefer numeric ints when the value is all digits to preserve existing numeric URLs.
    Returns integer id or None.
    """
    if not hid:
        return None
    # prefer plain numeric ids
    if isinstance(hid, str) and hid.isdigit():
        try:
            return int(hid)
        except Exception:
            pass
    try:
        from doctor import hashid as _hashid
        return _hashid.decode_hash(hid)
    except Exception:
        return None


# ─────────────────────────────────────────
# Search Patients + Family Members - FIXED
# ─────────────────────────────────────────

@role_required('doctor')
def search_patients(request):
    """Search for patients (main user or family member) - WORKING VERSION"""
    query = request.GET.get('q', '').strip()

    print(f" Searching for: '{query}'")

    if not query or len(query) < 2:
        return JsonResponse({'results': []})

    try:
        results = []

        # Search main patients
        print("  → Searching patients...")
        patients = Patient.objects.filter(
            Q(user__first_name__icontains=query) |
            Q(user__last_name__icontains=query) |
            Q(user__email__icontains=query) |
            Q(phone__icontains=query)
        ).select_related('user').values(
            'id', 'user__first_name', 'user__last_name', 'phone', 'user__email'
        )[:10]

        print(f" ✓ Found {patients.count()} patients")

        for p in patients:
            full_name = f"{p['user__first_name']} {p['user__last_name']}".strip() or p['user__email']
            results.append({
                'id': f"patient_{p['id']}",
                'name': full_name,
                'type': 'Main Patient',
                'phone': p['phone'] or 'N/A',
                'display': f"{full_name} (Main Patient) - {p['phone'] or 'No Phone'}"
            })

        #  Search family members
        print("  → Searching family members...")
        family_members = FamilyMember.objects.filter(
            Q(name__icontains=query) |
            Q(phone__icontains=query)
        ).select_related('patient__user').values(
            'id', 'name', 'relation', 'phone'
        )[:10]

        print(f"  ✓ Found {family_members.count()} family members")

        for fm in family_members:
            results.append({
                'id': f"family_{fm['id']}",
                'name': fm['name'],
                'type': f"Family Member ({fm['relation']})",
                'phone': fm['phone'] or 'N/A',
                'display': f"{fm['name']} ({fm['relation']}) - {fm['phone'] or 'No Phone'}"
            })

        print(f"Total results: {len(results)}")
        return JsonResponse({'results': results})

    except Exception as e:
        print(f" Error in search_patients: {str(e)}")
        import traceback
        traceback.print_exc()
        return JsonResponse({'error': f'Search error: {str(e)}'}, status=500)


# ─────────────────────────────────────────
# Slot Generator
# ─────────────────────────────────────────

def generate_slots(selected_date=None):
    clinic = ClinicSettings.get()
    start_time    = clinic.start_time
    end_time      = clinic.end_time
    lunch_start   = clinic.lunch_start
    lunch_end     = clinic.lunch_end
    interval      = clinic.slot_duration

    slots = []
    current = datetime.combine(datetime.today(), start_time)
    end_dt  = datetime.combine(datetime.today(), end_time)

    while current < end_dt:
        current_time = current.time()
        if lunch_start and lunch_end:
            if lunch_start <= current_time < lunch_end:
                current += timedelta(minutes=interval)
                continue
        slots.append(current_time)
        current += timedelta(minutes=interval)

    return slots


def get_slots(request):
    date_str = request.GET.get('appointment_date')

    if not date_str:
        return JsonResponse({'error': 'Date is required'})

    try:
        selected_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        return JsonResponse({'error': 'Invalid date format'})

    clinic = ClinicSettings.get()
    today = timezone.localdate()

    if selected_date < today:
        return JsonResponse({
            'slots': [],
            'message': 'Past date booking is not allowed'
        })

    max_booking_date = today + timedelta(days=30)
    if selected_date > max_booking_date:
        return JsonResponse({
            'slots': [],
            'message': 'Booking allowed only for next 30 days'
        })

    day_map = {
        0: 'mon', 1: 'tue', 2: 'wed', 3: 'thu',
        4: 'fri', 5: 'sat', 6: 'sun',
    }

    selected_day = day_map[selected_date.weekday()]

    if not clinic.is_working_day(selected_day):
        return JsonResponse({
            'slots': [],
            'message': 'Clinic is closed on this day'
        })

    start_time   = clinic.start_time
    end_time     = clinic.end_time
    lunch_start  = clinic.lunch_start
    lunch_end    = clinic.lunch_end
    interval     = clinic.slot_duration

    slots = []
    current = datetime.combine(datetime.today(), start_time)
    end_dt = datetime.combine(datetime.today(), end_time)

    while current < end_dt:
        current_time = current.time()
        if lunch_start and lunch_end:
            if lunch_start <= current_time < lunch_end:
                current += timedelta(minutes=interval)
                continue
        slots.append(current_time)
        current += timedelta(minutes=interval)

    # Apply Doctor Leave filtering
    from doctor.models import DoctorLeave, InnerMember
    doctor = InnerMember.objects.filter(role='doctor').first()
    if doctor:
        leave = DoctorLeave.objects.filter(doctor=doctor, date=selected_date).first()
        if leave:
            if leave.leave_type == 'full_day':
                slots = []
            elif leave.leave_type == 'first_half' and lunch_start:
                slots = [s for s in slots if s >= lunch_start]
            elif leave.leave_type == 'second_half' and lunch_start:
                slots = [s for s in slots if s < lunch_start]

    booked_slots = Appointment.booked_slots().filter(
        appointment_date=selected_date,
        is_archived=False
    ).values_list('time_slot', flat=True)

    booked_slots = [t.strftime("%H:%M") for t in booked_slots]

    now = timezone.localtime()
    filtered_slots = []

    for slot in slots:
        slot_str = slot.strftime("%H:%M")

        if (selected_date == now.date() and slot <= now.time()):
            continue

        if slot_str in booked_slots:
            continue

        display_time = datetime.strptime(
            slot_str, "%H:%M"
        ).strftime("%I:%M %p")

        filtered_slots.append(display_time)

    return JsonResponse({'slots': filtered_slots})

# Cancel Appointment (User Side)
@login_required
def cancel_appointment(request, hid):
    reason = ""
    if request.method == 'POST':
        try:
            payload = json.loads(request.body or "{}")
        except json.JSONDecodeError:
            payload = {}
        reason = (payload.get('cancellation_reason') or "").strip()

        if not reason:
            return JsonResponse({
                'success': False,
                'error': 'Cancellation reason is required.'
            }, status=400)

    appointment_id = resolve_hid(hid)

    appointment = get_object_or_404(
        Appointment,
        id=appointment_id,
        patient__user=request.user,
        is_archived=False
    )

    # Check 24-hour cancellation deadline
    appointment_datetime = datetime.combine(appointment.appointment_date, appointment.time_slot)
    if timezone.is_naive(appointment_datetime):
        appointment_datetime = timezone.make_aware(appointment_datetime)
    
    if (appointment_datetime - timezone.now()) < timedelta(hours=24):
        if request.method == 'POST':
            return JsonResponse({
                'success': False,
                'error': 'Cancellations are only allowed up to 24 hours before the appointment time.'
            }, status=400)
        messages.error(request, 'Cancellations are only allowed up to 24 hours before the appointment time.')
        return redirect('dashboard')

    # Only pending appointment can be cancelled
    if appointment.status == 'pending':
        appointment.status = 'cancelled'
        appointment.cancellation_reason = reason
        appointment.save(update_fields=['status', 'cancellation_reason'])
        if request.method == 'POST':
            return JsonResponse({
                'success': True,
                'status': appointment.get_status_display(),
                'status_raw': appointment.status,
                'appointment_date': appointment.appointment_date.isoformat(),
                'time_slot': appointment.time_slot.strftime("%I:%M %p"),
            })
        messages.success(request, 'Appointment cancelled successfully.')

    else:
        if request.method == 'POST':
            return JsonResponse({
                'success': False,
                'error': 'This appointment cannot be cancelled.'
            }, status=400)
        messages.error(request, 'This appointment cannot be cancelled.')

    return redirect('dashboard')


# Delete Appointment (Doctor Side)
@login_required
@role_required('doctor')
def delete_appointment(request, hid):
    if request.method == 'POST':
        appointment_id_val = resolve_hid(hid)

        appointment = get_object_or_404(Appointment, id=appointment_id_val, is_archived=False)
        appointment.delete()
        messages.success(request, 'Appointment deleted successfully.')
    return redirect('appointment:manage_appointments')


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

        appointments = Appointment.objects.filter(
    is_archived=False
)

        if search:
            appointments = appointments.filter(
                Q(patient__user__first_name__icontains=search) |
                Q(patient__user__last_name__icontains=search) |
                Q(patient__phone__icontains=search) |
                Q(family_member__name__icontains=search) |
                Q(family_member__phone__icontains=search)
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

        return render(request, 'doctor/manage_appointments.html', context)


@role_required('doctor')
def appointment_detail_modal(request, hid):
    appointment_id = resolve_hid(hid)

    appointment = get_object_or_404(Appointment, id=appointment_id, is_archived=False)
    visit        = Visit.objects.filter(appointment=appointment).first()
    prescription = None
    prescription_items = []

    if visit:
        prescription = Prescription.objects.filter(visit=visit).first()
        if prescription:
            prescription_items = prescription.items.select_related(
                'medicine_variant', 'medicine_variant__medicine'
            ).all()

    return render(request, 'doctor/appointment_detail.html', {
        'appointment'       : appointment,
        'visit'             : visit,
        'prescription'      : prescription,
        'prescription_items': prescription_items,
    })


# ─────────────────────────────────────────
# Add Appointment (Doctor) - UPDATED
# ─────────────────────────────────────────

@method_decorator([never_cache, role_required("doctor")], name="dispatch")
class Add_appointment(View):
    def get(self, request):
        return render(request, "doctor/add_appointment.html")

    def post(self, request):
        patient_selection = request.POST.get("patient_selection")
        appointment_date = request.POST.get("appointment_date")
        time_slot_raw    = request.POST.get("time_slot", "").strip()
        notes            = request.POST.get("notes")
        doctor           = InnerMember.objects.get(user=request.user)

        # Parse patient_selection
        if not patient_selection or '_' not in patient_selection:
            messages.error(request, "Please select a valid patient")
            return redirect('appointment:add_appointment')

        selection_type, selection_id = patient_selection.split('_', 1)

        patient = None
        family_member = None

        if selection_type == 'patient':
            try:
                patient = Patient.objects.get(id=selection_id)
            except Patient.DoesNotExist:
                messages.error(request, "Patient not found")
                return redirect('appointment:add_appointment')

        elif selection_type == 'family':
            try:
                family_member = FamilyMember.objects.get(id=selection_id)
                patient = family_member.patient
            except FamilyMember.DoesNotExist:
                messages.error(request, "Family member not found")
                return redirect('appointment:add_appointment')
        else:
            messages.error(request, "Invalid selection")
            return redirect('appointment:add_appointment')

        # Convert time to 24h format
        try:
            if "AM" in time_slot_raw.upper() or "PM" in time_slot_raw.upper():
                time_slot = datetime.strptime(time_slot_raw, "%I:%M %p").time()
            else:
                time_slot = datetime.strptime(time_slot_raw, "%H:%M").time()
        except ValueError:
            messages.error(request, "Invalid time format")
            return redirect('appointment:add_appointment')

        try:
            appointment_date_obj = datetime.strptime(appointment_date, "%Y-%m-%d").date()
        except ValueError:
            messages.error(request, "Invalid appointment date")
            return redirect('appointment:add_appointment')

        if Appointment.booked_slots().filter(
            is_archived=False,
            appointment_date=appointment_date_obj,
            time_slot=time_slot
        ).exists():
            messages.error(request, "This slot is already booked")
            return redirect('appointment:add_appointment')

        # Doctor Leave Check
        from doctor.models import DoctorLeave
        from clinic.models import ClinicSettings
        clinic = ClinicSettings.get()
        leave = DoctorLeave.objects.filter(doctor=doctor, date=appointment_date_obj).first()
        if leave:
            if leave.leave_type == 'full_day':
                messages.error(request, "Doctor is on leave on this date.")
                return redirect('appointment:add_appointment')
            elif leave.leave_type == 'first_half' and clinic.lunch_start and time_slot < clinic.lunch_start:
                messages.error(request, "Doctor is on leave during this time.")
                return redirect('appointment:add_appointment')
            elif leave.leave_type == 'second_half' and clinic.lunch_start and time_slot >= clinic.lunch_start:
                messages.error(request, "Doctor is on leave during this time.")
                return redirect('appointment:add_appointment')

        # Create appointment
        Appointment.objects.create(
            patient          = patient,
            family_member    = family_member,
            doctor           = doctor,
            appointment_date = appointment_date_obj,
            time_slot        = time_slot,
            notes            = notes,
            booked_by        = request.user,
        )

       
        return redirect('appointment:manage_appointments')


# ─────────────────────────────────────────
# Book Appointment (Patient)
# ─────────────────────────────────────────

@method_decorator(login_required(login_url='login'), name='dispatch')
class Book_appointment(View):

    def get(self, request):

        family_members = FamilyMember.objects.filter(
            patient=request.user.patient
        )

        return render(request, "appointment.html", {
            'family_members': family_members
        })

    def post(self, request):

        name             = request.POST.get('name', '').strip()
        appointment_date = request.POST.get("date")
        time_slot        = request.POST.get("time_slot", "").strip()
        notes            = request.POST.get("message")
        family_member_id = request.POST.get("family_member_id")

        # =========================
        # TIME CONVERSION FIX
        # =========================

        try:

            # 12-hour format
            if "AM" in time_slot.upper() or "PM" in time_slot.upper():

                parsed_time = datetime.strptime(
                    time_slot,
                    "%I:%M %p"
                )

            else:

                # 24-hour format
                parsed_time = datetime.strptime(
                    time_slot,
                    "%H:%M"
                )

            time_24 = parsed_time.time()

        except ValueError:

            messages.error(
                request,
                "Invalid time format"
            )

            return redirect('appointment:appointment')

        patient = Patient.objects.get(user=request.user)

        # Doctor fetch
        doctor = InnerMember.objects.filter(
            role='doctor'
        ).first()

        # Double booking prevention
        if Appointment.booked_slots().filter(
            is_archived=False,
            appointment_date=appointment_date,
            time_slot=time_24
        ).exists():

            messages.error(
                request,
                "This slot is already booked"
            )

            return redirect('appointment:appointment')

        # Doctor Leave Check
        from doctor.models import DoctorLeave
        from clinic.models import ClinicSettings
        clinic = ClinicSettings.get()
        leave = DoctorLeave.objects.filter(doctor=doctor, date=appointment_date).first()
        if leave:
            if leave.leave_type == 'full_day':
                messages.error(request, "Doctor is on leave on this date.")
                return redirect('appointment:appointment')
            elif leave.leave_type == 'first_half' and clinic.lunch_start and time_24 < clinic.lunch_start:
                messages.error(request, "Doctor is on leave during this time.")
                return redirect('appointment:appointment')
            elif leave.leave_type == 'second_half' and clinic.lunch_start and time_24 >= clinic.lunch_start:
                messages.error(request, "Doctor is on leave during this time.")
                return redirect('appointment:appointment')

        # Family member resolve
        family_member = None

        if family_member_id:

            try:

                family_member = FamilyMember.objects.get(
                    id=family_member_id,
                    patient=patient
                )

            except FamilyMember.DoesNotExist:

                family_member = None

        # =========================
        # CREATE APPOINTMENT
        # =========================

        Appointment.objects.create(

            patient=patient,
            family_member=family_member,
            doctor=doctor,

            # WHO BOOKED
            booked_by=request.user,

            appointment_date=appointment_date,

            # IMPORTANT
            time_slot=time_24,

            notes=notes,
        )

        return redirect('appointment:appointment')
    # ─────────────────────────────────────────
# Start Visit (Doctor)
# ─────────────────────────────────────────

@method_decorator([never_cache, role_required("doctor")], name="dispatch")
class StartVisitView(View):
    def get(self, request, hid):
        appointment_id = resolve_hid(hid)
        appointment = get_object_or_404(Appointment, id=appointment_id, is_archived=False)

        visit, created = Visit.objects.get_or_create(
            appointment=appointment,
            defaults={
                "patient": appointment.patient,
                "doctor": appointment.doctor,
                "visted_status": 'in_progress',
            }
        )

        # redirect using encoded hid so URL shows short id
        from doctor import hashid as _hashid
        return redirect("appointment:prescription", hid=_hashid.encode_id(visit.id))


# ─────────────────────────────────────────
# Prescription (Doctor)
# ─────────────────────────────────────────

@method_decorator([never_cache, role_required("doctor")], name="dispatch")
class PrescriptionView(View):
    def parse_dosage(self, dosage):
        try:
            parts = dosage.split(' (')
            dose_parts = [int(part) for part in parts[0].split('-')]
            meal = parts[1].replace(')', '')
        except Exception:
            dose_parts = []
            meal = 'after_food'

        morning = dose_parts[0] if len(dose_parts) > 0 else 0
        afternoon = dose_parts[1] if len(dose_parts) > 1 else 0
        evening = dose_parts[2] if len(dose_parts) > 3 else 0
        night_index = 3 if len(dose_parts) > 3 else 2
        night = dose_parts[night_index] if len(dose_parts) > night_index else 0

        return morning, afternoon, evening, night, meal

    def get(self, request, hid):
        visit_id = resolve_hid(hid)
        visit = get_object_or_404(Visit, id=visit_id)
        
        today = timezone.now().date()
        is_today = visit.appointment.appointment_date == today

        if visit.appointment.status == 'completed' and visit.visted_status != 'completed':
            visit.visted_status = 'completed'
            visit.save(update_fields=['visted_status'])

        prescription, _ = Prescription.objects.get_or_create(visit=visit)
        variants = MedicineVariant.objects.filter(medicine__is_active=True)
        items = prescription.items.select_related(
            'medicine_variant', 'medicine_variant__medicine'
        )
        lab_documents = visit.lab_documents.all()

        for item in items:
            morning, afternoon, evening, night, meal = self.parse_dosage(item.dosage)
            item.parsed_morning = morning
            item.parsed_afternoon = afternoon
            item.parsed_evening = evening
            item.parsed_night = night
            item.parsed_meal = meal

        return render(request, 'doctor/prescription.html', {
            'visit': visit,
            'variants': variants,
            'items': items,
            'lab_documents': lab_documents,
            'visit_completed': visit.visted_status == 'completed' or visit.appointment.status == 'completed',
            'is_today': is_today,
        })

    def reduce_stock(self, prescription):
        from datetime import datetime
        errors = []
        pending_items = prescription.items.select_related('medicine_variant__medicine').filter(
            should_deduct=True,
            was_deducted=False
        )
        
        for item in pending_items:
            variant = item.medicine_variant
            morning, afternoon, evening, night, _ = self.parse_dosage(item.dosage)

            total_qty = (morning + afternoon + evening + night) * item.days
            
            if total_qty <= 0:
                item.should_deduct, item.was_deducted = False, True
                item.save()
                continue
            
            if variant.stock >= total_qty:
                variant.stock -= total_qty
            else:
                errors.append(f"{variant.medicine.name}: Req {total_qty}, Avail {variant.stock}")
                variant.stock = 0
            
            variant.save()
            item.should_deduct, item.was_deducted = False, True
            item.save()
        
        return errors

    def post(self, request, hid):
        visit_id = resolve_hid(hid)
        visit = get_object_or_404(Visit, id=visit_id)
        visit.symptoms = request.POST.get("symptoms")
        visit.diagnosis = request.POST.get("diagnosis")
        visit.notes = request.POST.get("notes")

        is_completing = "complete_visit" in request.POST
        if is_completing:
            visit.visted_status = "completed"
        elif visit.visted_status != "completed":
            visit.visted_status = "in_progress"
        visit.save()

        prescription, _ = Prescription.objects.get_or_create(visit=visit)

        variant_ids = request.POST.getlist("variant_id[]")
        item_ids = request.POST.getlist("item_id[]")
        morning_list = request.POST.getlist("morning")
        afternoon_list = request.POST.getlist("afternoon")
        evening_list = request.POST.getlist("evening")
        night_list = request.POST.getlist("night")
        meal_list = request.POST.getlist("meal")
        days_list = request.POST.getlist("days")
        notes_list = request.POST.getlist("medicine_notes")
        deduct_list = request.POST.getlist("should_deduct[]")

        existing_item_ids = list(prescription.items.values_list('id', flat=True))
        submitted_item_ids = []

        for i, (item_id_str, v_id, m, a, e, n, meal, days, medicine_notes) in enumerate(zip(item_ids, variant_ids, morning_list, afternoon_list, evening_list, night_list, meal_list, days_list, notes_list)):
            if not v_id:
                continue
            variant = MedicineVariant.objects.get(id=v_id)
            dosage = f"{m}-{a}-{e}-{n} ({meal})"
            should_deduct = str(i) in deduct_list
            if item_id_str:
                try:
                    item_id_int = int(item_id_str)
                    submitted_item_ids.append(item_id_int)
                    item = PrescriptionItem.objects.get(id=item_id_int, prescription=prescription)
                    item.medicine_variant = variant
                    item.dosage = dosage
                    item.days = int(days)
                    item.notes = medicine_notes
                    item.should_deduct = should_deduct
                    item.save()
                except:
                    pass
            else:
                new_item = PrescriptionItem.objects.create(
                    prescription=prescription,
                    medicine_variant=variant,
                    dosage=dosage,
                    days=int(days),
                    notes=medicine_notes,
                    should_deduct=should_deduct,
                )
                submitted_item_ids.append(new_item.id)

        items_to_delete = set(existing_item_ids) - set(submitted_item_ids)
        if items_to_delete:
            PrescriptionItem.objects.filter(id__in=items_to_delete).delete()

        uploaded_documents = request.FILES.getlist("lab_documents")
        for document in uploaded_documents:
            LabDocument.objects.create(
                visit=visit,
                file=document,
                original_name=document.name,
                uploaded_by=request.user,
            )

        if uploaded_documents:
            messages.success(request, f"{len(uploaded_documents)} lab document(s) uploaded successfully.")

        if is_completing:
            stock_errors = self.reduce_stock(prescription)
            if stock_errors:
                for err in stock_errors:
                    messages.warning(request, f"Low stock: {err}")
            try:
                generate_bill_from_visit(visit)
                messages.success(request, "Bill generated successfully!")
            except Exception as e:
                print("BILL GENERATION ERROR:", str(e))
                messages.warning(request, f"Bill generation error: {str(e)}")
        else:
            new_bill_generated = False
            try:
                new_bill = generate_bill_from_visit(visit)
                if new_bill and new_bill.is_addon:
                    new_bill_generated = True
                    messages.info(request, f"Addon bill created for new medicines!")
            except Exception as e:
                print("ADDON BILL ERROR:", str(e))
                pass  # Silently fail for updates

        appointment = visit.appointment
        if is_completing:
            appointment.status = "completed"
        elif appointment.status != "completed":
            appointment.status = "confirmed"
        appointment.save()

        if is_completing or new_bill_generated:
            from doctor import hashid as _hashid
            return redirect('billing:bill_detail', hid=_hashid.encode_id(visit.id))
        
        if appointment.appointment_date == timezone.now().date():
            return redirect("doctor:dashboard")
        else:
            return redirect("appointment:manage_appointments")


# ─────────────────────────────────────────
# Appointment Detail (Patient)
# ─────────────────────────────────────────

@login_required(login_url='login')
def appointment_detail(request, hid):
    appointment_id = resolve_hid(hid)
    appointment = get_object_or_404(Appointment, id=appointment_id, patient=request.user.patient, is_archived=False)

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
