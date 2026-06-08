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
