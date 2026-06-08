# 🔍 Doctor Management System - Complete Audit Report
**Date:** June 8, 2026  
**Project:** Online Doctor Appointment System  
**Framework:** Django 6.0.4 with PostgreSQL

---

## 📋 Executive Summary

This is a Django-based clinic management system with appointment booking, billing, medicine inventory, and staff management. The project has **foundational structure but critical production-readiness issues**.

**Status:** ⚠️ **NOT PRODUCTION READY**

### Key Findings:
- 🔴 **3 Critical Bugs** preventing safe multi-user operation
- 🟠 **5 High-Priority Issues** causing data integrity problems
- 🟡 **8 Medium Issues** affecting reliability and security
- ✓ **Core features working** but need hardening

---

## 🔴 CRITICAL ISSUES (Must Fix Before Production)

<!-- ### 1. Race Condition in Bill Number Generation ⚠️ ACCOUNTING NIGHTMARE

**File:** [`billing/models.py`](billing/models.py#L53-L62)  
**Severity:** 🔴 CRITICAL

**Problem:**
```python
def save(self, *args, **kwargs):
    if not self.bill_number:
        with transaction.atomic():
            last = Bill.objects.select_for_update().order_by('-id').first()
            next_id = (last.id + 1) if last else 1  # ← BUG HERE
            self.bill_number = f'BILL-{next_id:04d}'
```

**Issues:**
1. Uses `id` instead of `COUNT()` - if bill ID#5 is deleted, next bill gets ID=5 again
2. `next_id = (last.id + 1)` can create duplicate bill numbers if billing gaps exist
3. Example: Bills 1,2,3,4 → delete 3,4 → Bill 5 created → next bill tries to get ID=6 but gets 4 because `order_by('-id').first()` gets bill 2
4. **Result:** Same bill number assigned twice → accounting chaos

**Fix Required:**
```python
def save(self, *args, **kwargs):
    if not self.bill_number:
        with transaction.atomic():
            # Count total bills instead of using max ID
            count = Bill.objects.count() + 1
            self.bill_number = f'BILL-{count:04d}'
```

**Impact:** 🔴
- Duplicate bill numbers in accounting
- Payment reconciliation failures
- Audit trail breaks
- Tax reporting errors

--- -->


<!-- ### 2. Double Booking Race Condition (Concurrent Requests)

**File:** [`appointment/views.py`](appointment/views.py#L440-L450)  
**Severity:** 🔴 CRITICAL (Multi-user)

**Problem:**
```python
# Check if slot booked
if Appointment.booked_slots().filter(
    appointment_date=appointment_date_obj,
    time_slot=time_slot
).exists():
    return "Slot already booked"

# ← RACE CONDITION: Slot could be booked here by another request

# Create appointment
Appointment.objects.create(...)  # Both create same appointment!
```

**Scenario:**
1. Request A: Checks slot 10:00 AM - available ✓
2. Request B: Checks slot 10:00 AM - available ✓
3. Request A: Creates appointment at 10:00 AM
4. Request B: Creates appointment at 10:00 AM (DUPLICATE)

**Fix Required:**
```python
# Option 1: Use select_for_update with unique constraint
with transaction.atomic():
    Appointment.objects.select_for_update().filter(
        appointment_date=appointment_date_obj,
        time_slot=time_slot,
        status__in=['pending', 'confirmed']
    ).exists()  # Lock the table

# Option 2: Add unique constraint to model
class Meta:
    constraints = [
        UniqueConstraint(
            fields=['appointment_date', 'time_slot', 'doctor'],
            condition=Q(is_archived=False, status__in=['pending', 'confirmed']),
            name='unique_appointment_slot'
        )
    ]
```

**Impact:** 🔴
- Multiple patients get same appointment slot
- Doctor overbooking
- Patient disappointment
- Operational chaos

--- -->


### 3. Patient Signal Handler Not Implemented ⚠️ USER CREATION BROKEN

**File:** [`accounts/models.py`](accounts/models.py#L4)  
**Status:** ❌ MISSING IMPLEMENTATION

**Problem:**
```python
from django.db.models.signals import post_save  # ← Imported but never used!
from django.dispatch import receiver            # ← Imported but never used!

class Patient(models.Model):
    """Patient profile auto-created from User via post_save signal"""
    # But signal handler is NOT DEFINED!
```

**Evidence:**
- `accounts/signals.py` does not exist (only `.pyc` file remains)
- No `@receiver(post_save, sender=User)` decorator anywhere
- `accounts/apps.py` has no `ready()` method to register signals

**What Should Happen:**
```python
# This code is MISSING:
@receiver(post_save, sender=User)
def create_patient_profile(sender, instance, created, **kwargs):
    if created:
        Patient.objects.create(user=instance)
```

**Current Reality:**
1. User registered via admin/form
2. **Patient NOT created** (no signal handler)
3. ForeignKey `Appointment.patient` → User fails
4. User cannot book appointments
5. 500 errors in appointment flow

**Fix:**
Create `accounts/signals.py`:
```python
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from .models import Patient

@receiver(post_save, sender=User)
def create_patient_profile(sender, instance, created, **kwargs):
    if created and not instance.is_staff:
        Patient.objects.get_or_create(user=instance)

@receiver(post_save, sender=User)
def save_patient_profile(sender, instance, **kwargs):
    if hasattr(instance, 'patient'):
        instance.patient.save()
```

Update `accounts/apps.py`:
```python
class AccountsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'accounts'
    
    def ready(self):
        import accounts.signals  # Register signals
```

**Impact:** 🔴
- Registration completely broken
- Impossible to test appointment flow
- API failures
- Users see 500 errors

---

## 🟠 HIGH-PRIORITY ISSUES

<!-- ### 4. Doctor Leave Filtering - Actually Implemented! ✅

**File:** [`appointment/views.py`](appointment/views.py#L198-L210)  
**Status:** ✅ ALREADY IMPLEMENTED

**Clarification:**
The previous audit incorrectly flagged this as incomplete. The `get_slots()` function *does* correctly filter out slots based on `leave.leave_type` (`full_day`, `first_half`, `second_half`) and passes the restricted slots to the frontend.

**Result:**
- Frontend properly hides slots when the doctor is on leave.
- User is prevented from booking during leave times correctly.
- This issue is resolved and working as intended!

--- -->

<!-- ### 5. Stock Deduction Not Implemented - Actually Implemented! ✅

**File:** [`appointment/views.py`](appointment/views.py#L730-L760)  
**Status:** ✅ ALREADY IMPLEMENTED

**Clarification:**
The previous audit incorrectly claimed stock deduction was missing because it only looked inside `billing/views.py`. However, the deduction logic is perfectly implemented in `appointment/views.py` inside the `reduce_stock()` method of `PrescriptionView`. 

It is even implemented securely using database locks (`select_for_update()`) and atomic transactions (`transaction.atomic()`) to prevent race conditions when updating the `MedicineVariant.stock`.

**Result:**
- When a prescription is completed, `reduce_stock()` is called.
- Stock is safely decreased.
- `was_deducted=True` flag is properly set so it doesn't deduct twice.
- This issue is resolved and working as intended!

--- -->

### 6. No Transaction Handling in Bill Generation

**File:** [`billing/views.py`](billing/views.py#L58-L120)  
**Status:** ❌ NOT ATOMIC

**Problem:**
```python
def generate_bill_from_visit(visit):
    """Creates BillItems but not in transaction"""
    
    for item in new_items:
        BillItem.objects.create(...)  # Each create is separate transaction
        # If error here, previous creates stay but this one fails
        # Result: Partial bill with incomplete items
    
    bill.subtotal = subtotal
    bill.save()  # Late update = inconsistency window
```

**Scenario:**
1. Bill created with 5 items
2. BillItems created: 1, 2, 3 ✓
3. Error creating BillItem 4 (invalid medicine variant)
4. Loop continues with items 5+ 
5. Bill saved with partial items
6. Billing report shows incomplete data

**Fix:**
```python
def generate_bill_from_visit(visit):
    from django.db import transaction
    
    with transaction.atomic():
        bill = Bill.objects.create(...)
        subtotal = 0
        
        for item in new_items:
            # If any error, entire transaction rolls back
            BillItem.objects.create(...)
            subtotal += item_price
        
        bill.subtotal = subtotal
        bill.save()
    
    return bill
```

---

## 🟡 MEDIUM-PRIORITY ISSUES

### 7. Bare Exception Handling & Silent Failures

**Locations:**
- [`doctor/views.py`](doctor/views.py#L24-32): Hashid decode fails silently
- [`expenses/views.py`](expenses/views.py#L40-50): Exception not logged
- [`appointment/views.py`](appointment/views.py#L60-65): Print statements instead of logging

**Problem:**
```python
def resolve_hid(hid):
    try:
        from doctor import hashid as _hashid
        return _hashid.decode_hash(str(hid))
    except Exception:  # ← Silent failure!
        pass
```

**Issues:**
- No logging = impossible to debug
- Errors cascade silently
- Invalid IDs cause confusing redirects
- Attacker could exploit to bypass checks

**Fix:**
```python
import logging
logger = logging.getLogger(__name__)

def resolve_hid(hid):
    try:
        from doctor import hashid as _hashid
        return _hashid.decode_hash(str(hid))
    except Exception as e:
        logger.warning(f"Hashid decode failed for {hid}: {e}")
        if isinstance(hid, str) and hid.isdigit():
            return int(hid)
    return None
```

---

### 8. Permissions Not Strict - Data Leakage

**File:** [`appointment/views.py:Manage_appointments`](appointment/views.py#L310)  
**Status:** ⚠️ INCOMPLETE CHECK

**Problem:**
```python
class Manage_appointments(View):
    def get(self, request):
        # Shows ALL appointments to ALL doctors!
        appointments = Appointment.objects.filter(is_archived=False)
        # No check: if appointment.doctor == current_doctor
```

**Current:** Doctor can see all clinic appointments (including those with other doctors)

**Should be:**
```python
doctor = InnerMember.objects.get(user=request.user)
appointments = Appointment.objects.filter(
    is_archived=False,
    doctor=doctor  # Only this doctor's appointments
)
```

---

### 9. No Rate Limiting - Brute Force Vulnerable

**Endpoints:**
- `search_patients()` - AJAX endpoint, can be hammered
- `get_slots()` - Can spam requests
- `login_view()` - No login throttling

**Problem:**
```python
@role_required('doctor')
def search_patients(request):
    query = request.GET.get('q', '').strip()
    # No rate limit check
    # Can make 1000s of requests
```

**Fix:** Use django-ratelimit or similar
```python
from django_ratelimit.decorators import ratelimit

@ratelimit(key='ip', rate='30/m')
@role_required('doctor')
def search_patients(request):
    ...
```

---

### 10. String Parsing Fragility in Bill Generation

**File:** [`billing/views.py`](billing/views.py#L95-100)

**Problem:**
```python
try:
    parts = item.dosage.split(' (')  # Expected format: "1-2 (mg)"
    dose_parts = [int(part) for part in parts[0].split('-')]
except Exception:
    dose_parts = []

qty = sum(dose_parts) * item.days  # If parsing failed: qty = 0
```

**Scenario:**
- Dosage: "one tablet twice daily" (text instead of numbers)
- Parsing fails silently → qty = 0
- BillItem created with quantity 0
- Bill shows ₹0 for medicine
- Revenue tracking broken

**Fix:** Validate dosage format at prescription creation:
```python
def validate_dosage(dosage):
    # Must be in format like "1-2" or "500"
    if not dosage:
        raise ValidationError("Dosage required")
    
    try:
        parts = dosage.split('-')
        for p in parts:
            int(p)  # Must be numeric
    except:
        raise ValidationError("Dosage must be numeric format (e.g., '1-2' or '500')")
```

---

## 🔵 SECURITY ISSUES

### 11. DEBUG = True Commented Out (But Still Vulnerable)

**File:** [`doctor_mgmt/settings.py`](doctor_mgmt/settings.py#L28)

```python
# SECURITY WARNING: don't run with debug turned on in production!
# DEBUG = True  # Commented but exposed in repo
# SECRET_KEY = 'django-insecure-...'  # Exposed in repo
```

**Risk:**
- If accidentally enabled → Full stack traces exposed
- SECRET_KEY in version control
- CSRF_TRUSTED_ORIGINS has ngrok URLs

<!-- ---

### 12. No Input Validation on File Uploads

**Locations:**
- `appointment/models.py:LabDocument`
- `appointment/models.py:PatientUploadedDocument`
- `doctor/views.py:upload_document()`

**Missing:**
- File size validation
- File type validation (allow PDF, block EXE)
- Path traversal protection
- Virus scanning

--- -->

## ⚠️ WORKFLOW ANALYSIS

### 🔴 Appointment Booking Flow (BROKEN)

```
1. Patient selects date
2. get_slots() called
   ├─ ✓ Checks clinic hours
   ├─ ✓ Skips lunch time
   ├─ ❌ Doesn't filter booked slots!
   └─ ❌ Doctor leave check incomplete
3. Patient sees ALL slots (even booked ones)
4. Patient selects slot
   ├─ ✓ Backend checks if booked
   ├─ ❌ But race condition exists
   └─ ❌ No unique constraint
5. Appointment created
   └─ 🔴 RESULT: Multiple bookings possible
```

**Fix Priority:** 🔴 HIGH

---

### 🟡 Bill Generation Flow (INCOMPLETE)

```
1. Visit completed
2. generate_bill_from_visit() called
   ├─ ✓ Creates bill
   ├─ ❌ No transaction.atomic()
   ├─ ❌ Stock never deducted
   └─ ❌ Fragile dosage parsing
3. BillItems created
   ├─ ✓ Medicine price captured
   └─ ❌ Partial bill if error
4. Bill.save()
   └─ 🟡 RESULT: Incomplete billing data
```

**Fix Priority:** 🟡 MEDIUM

---

### ✓ Doctor Login Flow (WORKING)

```
1. Doctor enters credentials ✓
2. User authenticated ✓
3. InnerMember role checked ✓
4. Redirected by role:
   ├─ doctor → dashboard ✓
   └─ biller → billing page ✓
5. Session stored ✓
```

**Status:** ✓ WORKING (but no login throttling)

---

### ❌ Patient Registration Flow (BROKEN)

```
1. User created (admin/form)
2. ❌ post_save signal NOT registered
3. Patient profile NOT created
4. Try to book appointment
   └─ 🔴 ForeignKey Patient missing → 500 Error
```

**Fix Priority:** 🔴 CRITICAL

---

## 📊 Database & Data Integrity

### FK Cascading Issues

| Model | Problem |
|-------|---------|
| `LabDocument` | `on_delete=CASCADE` - doc deleted with visit |
| `PatientUploadedDocument` | `on_delete=CASCADE` - doc deleted with patient |
| `PatientOldDocument` | `on_delete=CASCADE` - old records deleted |
| **Fix:** Use `SOFT_DELETE` or `SET_NULL` for audit trail |

### Missing Unique Constraints

```python
# Should have:
class Appointment(models.Model):
    class Meta:
        constraints = [
            UniqueConstraint(
                fields=['doctor', 'appointment_date', 'time_slot'],
                condition=Q(status__in=['pending', 'confirmed']),
                name='unique_active_appointment'
            )
        ]

# Should have:
class Bill(models.Model):
    bill_number = models.CharField(unique=True)  # Already has, but increment logic broken
```

---

## ✅ Features That ARE Working

| Feature | Status | Notes |
|---------|--------|-------|
| Patient search | ✓ Working | Basic name/phone search works |
| Role-based access | ✓ Working | doctor/biller roles enforced |
| Appointment CRUD | ✓ Working (but unsafe) | Create, read, update works |
| Medicine inventory | ✓ Working | CRUD operations work |
| Family member mgmt | ✓ Working | Add/edit/delete works |
| Clinic settings | ✓ Working | Time slots, lunch configured |
| Bill creation | ✓ Working (incomplete) | Bills created but stock not deducted |
| User authentication | ✓ Working | Login/logout works |

---

## 🚨 Production Checklist

### MUST FIX BEFORE LAUNCH:
- [ ] 🔴 Implement Patient signal handler (accounts/signals.py)
- [ ] 🔴 Fix bill number generation race condition
- [ ] 🔴 Add double booking prevention (unique constraint + atomic)
- [ ] 🟠 Implement stock deduction in bill generation
- [ ] 🟠 Add transaction handling to bill creation
- [ ] 🟠 Complete doctor leave filtering in get_slots()
- [ ] 🟠 Add input validation for file uploads
- [ ] 🟠 Add rate limiting to endpoints

### SHOULD FIX SOON:
- [ ] 🟡 Replace print() with proper logging
- [ ] 🟡 Add strict permission checks (doctor sees only own appointments)
- [ ] 🟡 Validate dosage format on prescription creation
- [ ] 🟡 Add soft delete for audit trail
- [ ] 🟡 Configure proper error handling

### NICE TO HAVE:
- [ ] 🔵 Email notifications
- [ ] 🔵 SMS reminders
- [ ] 🔵 Appointment confirmations
- [ ] 🔵 Online payment gateway
- [ ] 🔵 PDF generation
- [ ] 🔵 Analytics dashboard

---

## 📝 Code Quality Observations

### Positive Aspects:
- ✓ Good model design with proper relationships
- ✓ Indexes on appointment table
- ✓ Signal pattern imports (even if not implemented)
- ✓ Clinic settings singleton well designed
- ✓ Addon bill tracking clever
- ✓ Doctor leave model exists

### Negative Aspects:
- ❌ Inconsistent error handling
- ❌ Hardcoded strings ('mon', 'tue', etc.)
- ❌ Print debugging in production code
- ❌ Silent exception swallowing
- ❌ No logging infrastructure
- ❌ Pagination hardcoded (10, 20, 30)
- ❌ Repeated slot generation code
- ❌ Hashid decode logic duplicated

---

## 🎯 Recommended Fix Priority

### Phase 1 (Critical - Do First):
1. Implement Patient signal handler → Unblock registration
2. Fix bill number generation → Fix accounting
3. Add appointment unique constraint → Fix double booking
4. Implement stock deduction → Fix inventory

**Estimated Time:** 6-8 hours

### Phase 2 (High - Do Second):
1. Complete doctor leave filtering
2. Add transaction handling to bill creation
3. Add rate limiting
4. Strict permission checks

**Estimated Time:** 4-6 hours

### Phase 3 (Medium - Do Third):
1. Input validation & file upload security
2. Logging infrastructure
3. Error handling improvements
4. Code deduplication

**Estimated Time:** 8-10 hours

### Phase 4 (Nice to Have):
- Email notifications
- Payment gateway
- Advanced features

**Estimated Time:** 40+ hours

---

## 📞 Recommendations

1. **Add logging immediately:**
   ```python
   # settings.py
   LOGGING = {
       'version': 1,
       'disable_existing_loggers': False,
       'handlers': {
           'file': {
               'level': 'ERROR',
               'class': 'logging.FileHandler',
               'filename': 'error.log',
           },
       },
       'root': {
           'handlers': ['file'],
           'level': 'ERROR',
       },
   }
   ```

2. **Use Django's built-in validations:**
   - Replace `except Exception:` with specific exceptions
   - Use model validators for business logic

3. **Write integration tests for critical flows:**
   - Appointment booking (concurrent)
   - Bill generation
   - Patient registration

4. **Use database constraints for enforcement:**
   - Not just application logic
   - Forces data integrity at DB level

5. **Consider async tasks:**
   - Stock updates
   - Notifications
   - Report generation

---

## 📄 Files Analyzed

- ✓ `doctor_mgmt/settings.py` - Configuration
- ✓ `doctor_mgmt/urls.py` - Routing
- ✓ `accounts/` - User management
- ✓ `appointment/` - Booking & visits
- ✓ `billing/` - Bill generation
- ✓ `doctor/` - Doctor portal
- ✓ `medicine/` - Inventory
- ✓ `clinic/` - Settings
- ✓ `expenses/` - Expense tracking

---

**Report Generated:** June 8, 2026  
**Auditor:** AI Code Audit Agent  
**Status:** Complete
