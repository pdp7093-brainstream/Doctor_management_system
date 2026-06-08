# 🔧 Critical Bugs - Quick Fix Guide

## Bug #1: Patient Signal Handler Missing
**Priority:** 🔴 CRITICAL  
**Time to Fix:** 15 minutes  
**Impact:** Registration completely broken

### The Problem
When a user is created, no Patient profile is auto-created because the signal handler doesn't exist.

### Quick Fix

**Step 1:** Create `accounts/signals.py`
```python
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from .models import Patient

@receiver(post_save, sender=User)
def create_patient_profile(sender, instance, created, **kwargs):
    """Auto-create Patient profile when User is created"""
    if created and not instance.is_staff:
        Patient.objects.get_or_create(user=instance)

@receiver(post_save, sender=User)
def save_patient_profile(sender, instance, **kwargs):
    """Save Patient profile when User is saved"""
    if hasattr(instance, 'patient'):
        instance.patient.save()
```

**Step 2:** Update `accounts/apps.py`
```python
from django.apps import AppConfig

class AccountsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'accounts'
    
    def ready(self):
        import accounts.signals  # Register signals when app is ready
```

**Step 3:** Verify in `accounts/__init__.py` (add if empty):
```python
default_app_config = 'accounts.apps.AccountsConfig'
```

### Test It
```bash
python manage.py shell
from django.contrib.auth.models import User
u = User.objects.create_user('testuser', 'test@example.com', 'password123')
from accounts.models import Patient
Patient.objects.filter(user=u).exists()  # Should be True
```

---

## Bug #2: Bill Number Race Condition
**Priority:** 🔴 CRITICAL  
**Time to Fix:** 20 minutes  
**Impact:** Accounting errors, duplicate bill numbers

### The Problem
Bill numbers can be duplicated when bills are deleted, creating accounting nightmares.

### Quick Fix

**File:** `billing/models.py`

Replace the `save()` method:
```python
def save(self, *args, **kwargs):
    from decimal import Decimal
    from django.db import transaction
    
    # GST + Total calculation (keep this part)
    self.gst_amount = (self.subtotal * self.gst_percent) / Decimal('100')
    self.total = self.consultation_fee + self.subtotal + self.gst_amount - self.discount

    # FIX: Use count-based bill numbers instead of max ID
    if not self.bill_number:
        with transaction.atomic():
            # Count all bills including deleted ones for sequential numbering
            count = Bill.objects.count() + 1
            self.bill_number = f'BILL-{count:04d}'
            super().save(*args, **kwargs)
    else:
        super().save(*args, **kwargs)
```

### Test It
```bash
python manage.py shell
from billing.models import Bill
from appointment.models import Visit

# Create test visit and bills
b1 = Bill.objects.create(visit=visit_obj, subtotal=100)
print(b1.bill_number)  # Should be BILL-0001

b2 = Bill.objects.create(visit=visit_obj, subtotal=200)
print(b2.bill_number)  # Should be BILL-0002

b1.delete()

b3 = Bill.objects.create(visit=visit_obj, subtotal=300)
print(b3.bill_number)  # Should be BILL-0003 (NOT BILL-0001)
```

---

## Bug #3: Double Booking Race Condition
**Priority:** 🔴 CRITICAL  
**Time to Fix:** 30 minutes  
**Impact:** Appointment conflicts, overbooking

### The Problem
Two concurrent requests can book the same appointment slot.

### Quick Fix

**Option A: Add Unique Constraint (Recommended)**

**File:** `appointment/models.py`

```python
from django.db import models
from django.db.models import Q, UniqueConstraint

class Appointment(models.Model):
    # ... existing fields ...
    
    class Meta:
        indexes = [
            models.Index(fields=['appointment_date', 'time_slot'], name='appt_date_time_idx'),
            models.Index(fields=['appointment_date', 'status'], name='appt_date_status_idx'),
            models.Index(fields=['status'], name='appt_status_idx'),
            models.Index(fields=['doctor', 'appointment_date'], name='appt_doctor_date_idx'),
        ]
        # ADD THIS CONSTRAINT:
        constraints = [
            UniqueConstraint(
                fields=['doctor', 'appointment_date', 'time_slot'],
                condition=Q(is_archived=False) & Q(status__in=['pending', 'confirmed']),
                name='unique_active_appointment_slot'
            )
        ]
```

Then create migration:
```bash
python manage.py makemigrations
python manage.py migrate
```

**Option B: Add Application-Level Lock (Fallback)**

**File:** `appointment/views.py` in `Add_appointment.post()`

Replace the appointment creation:
```python
from django.db import transaction, IntegrityError

# Instead of:
# Appointment.objects.create(...)

# Do this:
try:
    with transaction.atomic():
        # Lock the slot
        Appointment.objects.select_for_update().filter(
            doctor=doctor,
            appointment_date=appointment_date_obj,
            time_slot=time_slot,
            is_archived=False,
            status__in=['pending', 'confirmed']
        ).exists()
        
        # Create only if still available
        appt = Appointment.objects.create(
            patient=patient,
            family_member=family_member,
            doctor=doctor,
            appointment_date=appointment_date_obj,
            time_slot=time_slot,
            notes=notes,
            booked_by=request.user,
        )
except IntegrityError:
    messages.error(request, "Slot just booked by another user. Please choose a different time.")
    return redirect('appointment:add_appointment')
```

### Test It
```python
# Simulate concurrent requests
from threading import Thread
from django.contrib.auth.models import User
from doctor.models import InnerMember
from appointment.models import Appointment

def book_slot(doctor_id, date, time):
    from appointment.views import Add_appointment
    view = Add_appointment()
    # Try to book same slot...
    
# This should now fail on the second attempt
```

---

## Bug #4: Stock Deduction Missing
**Priority:** 🟠 HIGH  
**Time to Fix:** 25 minutes  
**Impact:** Inventory tracking broken

### The Problem
When bills are generated, medicine stock is never reduced.

### Quick Fix

**File:** `billing/views.py`

Find `generate_bill_from_visit()` function and update the loop:

```python
def generate_bill_from_visit(visit):
    """Automatically generate bill when visit is completed"""
    from django.utils import timezone
    
    prescription = getattr(visit, 'prescription', None)
    if not prescription:
        return None

    new_items = prescription.items.select_related(
        'medicine_variant__medicine'
    ).filter(billed_on__isnull=True)

    existing_bill = Bill.objects.filter(visit=visit, is_addon=False, is_archived=False).first()
    
    clinic = ClinicSettings.get()
    subtotal = Decimal('0')

    # Determine consultation fee...
    consultation_fee = clinic.default_consultation_fee
    appt = getattr(visit, 'appointment', None)
    appt_type = getattr(appt, 'consultation_type', None)
    if appt_type == 'phone':
        consultation_fee = getattr(clinic, 'phone_consultation_fee', clinic.default_consultation_fee)
    elif appt_type == 'video':
        consultation_fee = getattr(clinic, 'video_consultation_fee', clinic.default_consultation_fee)

    if not new_items.exists():
        if not existing_bill:
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

    # Determine if addon or original bill
    if existing_bill:
        bill = Bill.objects.create(
            visit=visit,
            subtotal=0,
            gst_percent=clinic.default_gst,
            consultation_fee=0,
            is_addon=True,
            parent_bill=existing_bill,
            notes="Prescription amendment/addon"
        )
    else:
        bill = Bill.objects.create(
            visit=visit,
            subtotal=0,
            gst_percent=clinic.default_gst,
            consultation_fee=consultation_fee,
            is_addon=False
        )

    # Process each prescription item
    for item in new_items:
        variant = item.medicine_variant
        if not variant:
            continue

        # Parse dosage
        try:
            parts = item.dosage.split(' (')
            dose_parts = [int(part) for part in parts[0].split('-')]
        except Exception:
            dose_parts = []

        qty = sum(dose_parts) * item.days

        # ========== ADD THIS BLOCK ==========
        # DEDUCT STOCK from medicine variant
        if qty > 0 and item.should_deduct:
            if variant.stock >= qty:
                variant.stock -= qty
                variant.save()
                item.was_deducted = True
            elif variant.stock > 0:
                # Partial deduction if low stock
                qty_deducted = variant.stock
                variant.stock = 0
                variant.save()
                item.was_deducted = True
                # Log warning
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f"Partial stock deduction for {variant.medicine.name}: deducted {qty_deducted}, needed {qty}")
            else:
                # Out of stock warning
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f"Out of stock: {variant.medicine.name} (needed {qty})")
        
        item.billed_on = timezone.now()
        item.bill_id = bill.id
        item.save()
        # ========== END ADD BLOCK ==========

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
```

### Test It
```bash
python manage.py shell
from medicine.models import MedicineVariant
from appointment.models import PrescriptionItem, Prescription

# Check initial stock
variant = MedicineVariant.objects.first()
print(f"Before: {variant.stock}")  # e.g., 100

# Create prescription with this variant
# When bill is generated, stock should decrease

print(f"After: {variant.stock}")  # Should be less than 100
```

---

## Bug #5: Bill Creation Not Atomic
**Priority:** 🟠 HIGH  
**Time to Fix:** 20 minutes  
**Impact:** Partial bills if errors occur

### The Problem
Bill creation isn't wrapped in a transaction, so if an error occurs mid-creation, partial data remains.

### Quick Fix

**File:** `billing/views.py`

Wrap the bill creation in transaction:

```python
from django.db import transaction

def generate_bill_from_visit(visit):
    """Automatically generate bill when visit is completed"""
    
    # ... validation code ...
    
    # WRAP IN TRANSACTION
    try:
        with transaction.atomic():
            if existing_bill:
                bill = Bill.objects.create(...)
            else:
                bill = Bill.objects.create(...)

            for item in new_items:
                # ... all processing ...
                BillItem.objects.create(...)
                subtotal += total
            
            bill.subtotal = subtotal
            bill.save()
            
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Bill creation failed for visit {visit.id}: {e}")
        # All changes rolled back automatically
        return None
    
    return bill
```

---

## Bug #6: Doctor Leave Filtering Incomplete
**Priority:** 🟠 HIGH  
**Time to Fix:** 15 minutes  
**Impact:** Doctor availability not checked

### The Problem
The `get_slots()` function doesn't actually filter out slots based on doctor leave.

### Quick Fix

**File:** `appointment/views.py`

Find the `get_slots()` function and complete the filtering:

```python
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

    start_time = clinic.start_time
    end_time = clinic.end_time
    lunch_start = clinic.lunch_start
    lunch_end = clinic.lunch_end
    interval = clinic.slot_duration

    slots = []
    current = datetime.combine(datetime.today(), start_time)
    end_dt = datetime.combine(datetime.today(), end_time)

    while current < end_dt:
        current_time = current.time()
        
        # Skip lunch time
        if lunch_start and lunch_end:
            if lunch_start <= current_time < lunch_end:
                current += timedelta(minutes=interval)
                continue
        
        slots.append(current_time)
        current += timedelta(minutes=interval)

    # ========== ADD THIS BLOCK ==========
    # Filter out booked slots
    booked_slots = Appointment.booked_slots().filter(
        appointment_date=selected_date,
        is_archived=False
    ).values_list('time_slot', flat=True)
    
    slots = [s for s in slots if s not in booked_slots]
    
    # Filter based on doctor leave
    from doctor.models import DoctorLeave, InnerMember
    doctor = InnerMember.objects.filter(role='doctor').first()
    
    if doctor:
        leave = DoctorLeave.objects.filter(doctor=doctor, date=selected_date).first()
        if leave:
            if leave.leave_type == 'full_day':
                # No slots available
                return JsonResponse({
                    'slots': [],
                    'message': 'Doctor is on leave on this day'
                })
            elif leave.leave_type == 'first_half':
                # Remove slots before lunch
                slots = [s for s in slots if lunch_start and s >= lunch_start]
            elif leave.leave_type == 'second_half':
                # Remove slots after lunch
                slots = [s for s in slots if lunch_start and s < lunch_start]
    # ========== END ADD BLOCK ==========

    return JsonResponse({'slots': [str(s) for s in slots]})
```

---

## Summary of Fixes

| Bug | Fix Time | Status |
|-----|----------|--------|
| Patient signal | 15 min | 📍 Start here |
| Bill number race | 20 min | 📍 Then this |
| Double booking | 30 min | 📍 Then this |
| Stock deduction | 25 min | 📍 Then this |
| Bill atomicity | 20 min | 📍 Then this |
| Doctor leave | 15 min | 📍 Finish with this |

**Total Time to Fix All Critical Bugs:** ~2 hours

---

## Testing Checklist

After applying fixes:

```bash
# Run tests
python manage.py test

# Or manually test:
python manage.py shell

# Test 1: Patient creation
from django.contrib.auth.models import User
u = User.objects.create_user('test', 'test@test.com', 'pass')
from accounts.models import Patient
print(Patient.objects.filter(user=u).exists())  # Should be True

# Test 2: Bill numbers
from billing.models import Bill
from appointment.models import Visit
b1 = Bill.objects.create(visit=visit_obj, subtotal=100)
b2 = Bill.objects.create(visit=visit_obj, subtotal=200)
print(b1.bill_number, b2.bill_number)  # Should be sequential

# Test 3: Stock deduction
from medicine.models import MedicineVariant
print(variant.stock)  # Should decrease after bill

# Test 4: Available slots
from appointment.views import get_slots
# Should not show booked/leave slots
```

---

**Next Steps:**
1. Apply fixes in order
2. Run tests after each fix
3. Deploy to staging first
4. Then to production
