# 📊 System Flows & Architecture

## Overall System Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                     Doctor Management System                         │
│                                                                      │
│  Django 6.0.4 + PostgreSQL                                         │
└─────────────────────────────────────────────────────────────────────┘

┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐
│   Public Site    │  │  Doctor Portal   │  │  Biller Portal   │
│  (Patients)      │  │  (Doctors)       │  │  (Billers)       │
└────────┬─────────┘  └────────┬─────────┘  └────────┬─────────┘
         │                     │                     │
         └─────────────────────┼─────────────────────┘
                               │
         ┌─────────────────────┴─────────────────────┐
         │                                           │
    ┌────▼──────┐  ┌──────────┐  ┌───────────┐  ┌──▼──────┐
    │ Accounts  │  │Appointment│ │  Billing  │  │Medicine │
    │ (Users)   │  │ (Bookings)│ │  (Bills)  │  │(Inventory)
    └─────┬──────┘  └───┬──────┘  └─────┬────┘  └────┬────┘
          │              │               │            │
          └──────────────┼───────────────┼────────────┘
                         │               │
                    ┌────▼───────────────▼───┐
                    │   PostgreSQL Database  │
                    └────────────────────────┘
```

---

## 🔴 APPOINTMENT BOOKING FLOW (BROKEN)

### Current Flow (WITH BUGS)

```
┌─────────────────────────────────────────────────────────────────────┐
│                     Patient Books Appointment                        │
└─────────────────────────────────────────────────────────────────────┘
                            │
                            ▼
        ┌──────────────────────────────────────┐
        │  Select Date & Time                  │
        │  Click "View Available Slots"        │
        └────────────┬─────────────────────────┘
                     │
                     ▼ Frontend calls: GET /appointment/get_slots/?date=YYYY-MM-DD
        ┌──────────────────────────────────────┐
        │  get_slots() Function                │
        │  ✓ Checks clinic hours               │
        │  ✓ Skips lunch time                  │
        │  ✓ Checks if working day             │
        │  ❌ DOES NOT filter booked slots!   │
        │  ❌ Doctor leave check incomplete    │
        └────────────┬─────────────────────────┘
                     │
                     ▼ Returns ALL slots (even booked ones)
        ┌──────────────────────────────────────┐
        │  Frontend Shows All Time Slots       │
        │  (even already booked ones)          │
        │  Patient selects: 10:00 AM ← MISTAKE │
        └────────────┬─────────────────────────┘
                     │
                     ▼ Frontend POSTs to /appointment/book/
        ┌──────────────────────────────────────┐
        │  Book_appointment.post()             │
        │                                      │
        │  Check: Is slot booked?              │
        │  ┌────────────────────────────────┐  │
        │  │if Appointment.booked_slots()   │  │
        │  │  .filter(slot).exists():       │  │
        │  │    return error                │  │
        │  └────────────────────────────────┘  │
        │                ↓                     │
        │    ┌──────────────────────────────┐  │
        │    │ ❌ RACE CONDITION HERE       │  │
        │    │                              │  │
        │    │ Request A: Check ✓ available│  │
        │    │ Request B: Check ✓ available│  │
        │    │ Request A: Create ✓ success │  │
        │    │ Request B: Create ✓ success │  │
        │    │                              │  │
        │    │ Result: DOUBLE BOOKING!     │  │
        │    └──────────────────────────────┘  │
        │                                      │
        │  Appointment.objects.create()        │
        │  Create in DB                        │
        └────────────┬─────────────────────────┘
                     │
                     ▼
        ┌──────────────────────────────────────┐
        │  Appointment Created                 │
        │  Status: Pending                     │
        │  Date: 2026-06-10                    │
        │  Time: 10:00 AM                      │
        │  🔴 BUT SLOT ALREADY TAKEN!          │
        └──────────────────────────────────────┘
                     │
                     ▼
        ┌──────────────────────────────────────┐
        │  Result: 2 Patients @ 10:00 AM       │
        │  Doctor Confused                     │
        │  Patient Missed Appointment          │
        │  🔴 OPERATIONAL CHAOS                │
        └──────────────────────────────────────┘
```

### Fixed Flow (WITH FIXES)

```
┌─────────────────────────────────────────────────────────────────────┐
│                     Patient Books Appointment                        │
└─────────────────────────────────────────────────────────────────────┘
                            │
                            ▼
        ┌──────────────────────────────────────┐
        │  Select Date & Time                  │
        │  Click "View Available Slots"        │
        └────────────┬─────────────────────────┘
                     │
                     ▼ Frontend calls: GET /appointment/get_slots/?date=YYYY-MM-DD
        ┌──────────────────────────────────────┐
        │  get_slots() Function [FIXED]        │
        │  ✓ Checks clinic hours               │
        │  ✓ Skips lunch time                  │
        │  ✓ Checks if working day             │
        │  ✓ FILTERS OUT booked slots!         │
        │  ✓ FILTERS OUT doctor leave!         │
        └────────────┬─────────────────────────┘
                     │
                     ▼ Returns ONLY available slots
        ┌──────────────────────────────────────┐
        │  Frontend Shows Only Free Slots      │
        │  Patient selects: 10:30 AM (available)
        └────────────┬─────────────────────────┘
                     │
                     ▼ Frontend POSTs to /appointment/book/
        ┌──────────────────────────────────────┐
        │  Add_appointment.post() [FIXED]      │
        │                                      │
        │  with transaction.atomic():          │
        │    select_for_update() LOCK slot     │
        │    ✓ No one else can take it         │
        │                                      │
        │    Check: Is slot still free?        │
        │    ✓ Yes, create                     │
        │    ✗ No, rollback + error            │
        │                                      │
        │  Unique constraint enforced!         │
        │  DB prevents duplicate                │
        └────────────┬─────────────────────────┘
                     │
                     ▼
        ┌──────────────────────────────────────┐
        │  Appointment Created                 │
        │  Status: Pending                     │
        │  ✓ Slot is GUARANTEED free           │
        │  ✓ No double booking                 │
        │  ✓ Doctor available                  │
        │  ✓ Time: 10:30 AM                    │
        └──────────────────────────────────────┘
                     │
                     ▼
        ┌──────────────────────────────────────┐
        │  Success: Single Booking             │
        │  Patient gets appointment            │
        │  Doctor sees in schedule             │
        │  ✓ OPERATIONAL INTEGRITY             │
        └──────────────────────────────────────┘
```

---

## 🟡 BILL GENERATION FLOW (INCOMPLETE)

### Current Flow (WITH BUGS)

```
┌─────────────────────────────────────────────────────────────────────┐
│                     Visit Completed                                 │
│              Doctor enters Diagnosis & Prescription                 │
└─────────────────────────────────────────────────────────────────────┘
                            │
                            ▼
        ┌──────────────────────────────────────┐
        │  Doctor clicks "Generate Bill"       │
        │  Calls: generate_bill_from_visit()   │
        └────────────┬─────────────────────────┘
                     │
                     ▼
        ┌──────────────────────────────────────┐
        │  Get Prescription Items              │
        │  - Item 1: Aspirin 500mg x 10 days   │
        │  - Item 2: Cough syrup x 5 days      │
        │  - Item 3: Antibiotic x 7 days       │
        └────────────┬─────────────────────────┘
                     │
                     ▼
        ┌──────────────────────────────────────┐
        │  ❌ NO TRANSACTION LOCK!             │
        │  Create Bill (empty)                 │
        │  bill_number = BILL-0050             │
        │  subtotal = ₹0                       │
        │  status = unpaid                     │
        └────────────┬─────────────────────────┘
                     │
                     ▼
        ┌──────────────────────────────────────┐
        │  Loop: Create BillItems              │
        │  ❌ NOT in transaction.atomic()      │
        │                                      │
        │  Item 1: Create ✓                    │
        │  Item 2: Create ✓                    │
        │  ❌ Item 3: ERROR! (Bad dosage)     │
        │  Items 4+: Skip                      │
        │                                      │
        │  Result: Partial bill created!       │
        └────────────┬─────────────────────────┘
                     │
                     ▼
        ┌──────────────────────────────────────┐
        │  ❌ STOCK NEVER DEDUCTED!            │
        │                                      │
        │  Medicine Inventory:                 │
        │  - Aspirin: was 100, still 100 ❌   │
        │  - Cough syrup: was 50, still 50 ❌│
        │  - Antibiotic: was 200, still 200 ❌│
        │                                      │
        │  System shows medicine in stock      │
        │  But clinic is actually out!         │
        └────────────┬─────────────────────────┘
                     │
                     ▼
        ┌──────────────────────────────────────┐
        │  Bill Calculation                    │
        │  Items: 2 (Item 3 missing)           │
        │  Subtotal: ₹450 (incomplete!)        │
        │  Tax: ₹81                            │
        │  Total: ₹531                         │
        │                                      │
        │  🔴 Revenue incomplete!              │
        │  🔴 Stock records wrong!             │
        │  🔴 Patient charged incomplete!      │
        └──────────────────────────────────────┘
                     │
                     ▼
        ┌──────────────────────────────────────┐
        │  Later: Stock Report                 │
        │  System says: Aspirin 100 in stock   │
        │  Clinic says: We have 5!             │
        │  Accounting says: Revenue short      │
        │  🔴 DATA INTEGRITY BROKEN            │
        └──────────────────────────────────────┘
```

### Fixed Flow (WITH FIXES)

```
┌─────────────────────────────────────────────────────────────────────┐
│                     Visit Completed                                 │
│              Doctor enters Diagnosis & Prescription                 │
└─────────────────────────────────────────────────────────────────────┘
                            │
                            ▼
        ┌──────────────────────────────────────┐
        │  Doctor clicks "Generate Bill"       │
        │  Calls: generate_bill_from_visit()   │
        └────────────┬─────────────────────────┘
                     │
                     ▼ ✓ WRAPPED IN transaction.atomic()
        ┌──────────────────────────────────────┐
        │  BEGIN TRANSACTION [FIXED]           │
        │  All or nothing!                     │
        └────────────┬─────────────────────────┘
                     │
                     ▼
        ┌──────────────────────────────────────┐
        │  Create Bill                         │
        │  bill_number = BILL-0050             │
        │  subtotal = ₹0 (temp)                │
        └────────────┬─────────────────────────┘
                     │
                     ▼
        ┌──────────────────────────────────────┐
        │  Loop: Create BillItems [FIXED]      │
        │  ✓ ALL in same transaction           │
        │                                      │
        │  Item 1:                             │
        │    - BillItem created ✓              │
        │    - Aspirin stock: 100 → 90 ✓      │
        │    - Price: ₹150 ✓                   │
        │                                      │
        │  Item 2:                             │
        │    - BillItem created ✓              │
        │    - Cough syrup: 50 → 45 ✓         │
        │    - Price: ₹300 ✓                   │
        │                                      │
        │  Item 3:                             │
        │    - ERROR! Bad dosage format        │
        │    ❌ ENTIRE TRANSACTION ROLLED BACK│
        │    All changes reverted              │
        │    Stock back to original            │
        └────────────┬─────────────────────────┘
                     │
                     ▼
        ┌──────────────────────────────────────┐
        │  Option A: Bill NOT created          │
        │  User must fix prescription & retry  │
        │                                      │
        │  Option B: Skip invalid item         │
        │  (After validation)                  │
        │  Retry with 2 valid items            │
        └────────────┬─────────────────────────┘
                     │
                     ▼
        ┌──────────────────────────────────────┐
        │  Final Bill Calculation              │
        │  Items: 2 (validated)                │
        │  Subtotal: ₹450 ✓                    │
        │  Tax: ₹81 ✓                          │
        │  Total: ₹531 ✓                       │
        │                                      │
        │  Stock After:                        │
        │  - Aspirin: 90 (down from 100) ✓    │
        │  - Cough syrup: 45 (down from 50) ✓│
        │                                      │
        │  COMMIT TRANSACTION                  │
        │  ✓ Data consistent                   │
        │  ✓ Stock accurate                    │
        │  ✓ Revenue complete                  │
        └──────────────────────────────────────┘
```

---

## ❌ PATIENT REGISTRATION FLOW (BROKEN)

### Current (Missing Signal)

```
┌─────────────────────────────────────────────────────────────────────┐
│                     Patient Registration                            │
└─────────────────────────────────────────────────────────────────────┘
                            │
                            ▼
        ┌──────────────────────────────────────┐
        │  User submits registration form      │
        │  username: john_doe                  │
        │  email: john@example.com             │
        │  password: secret123                 │
        └────────────┬─────────────────────────┘
                     │
                     ▼
        ┌──────────────────────────────────────┐
        │  Django creates User object          │
        │  Triggers: post_save signal          │
        └────────────┬─────────────────────────┘
                     │
                     ▼
        ┌──────────────────────────────────────┐
        │  ❌ SIGNAL HANDLER NOT REGISTERED    │
        │                                      │
        │  accounts/signals.py: MISSING        │
        │  accounts/apps.py: No ready()        │
        │  accounts/__init__.py: Empty         │
        │                                      │
        │  Signal fires but no one listening!  │
        └────────────┬─────────────────────────┘
                     │
                     ▼
        ┌──────────────────────────────────────┐
        │  Patient profile NOT created         │
        │  Database state:                     │
        │                                      │
        │  ✓ User table:                       │
        │    id=1, username=john_doe           │
        │                                      │
        │  ❌ Patient table:                   │
        │    (empty - no entry!)               │
        └────────────┬─────────────────────────┘
                     │
                     ▼
        ┌──────────────────────────────────────┐
        │  User tries to book appointment      │
        │  Calls: Book_appointment.get()       │
        │  Accesses: request.user.patient      │
        │                                      │
        │  ❌ AttributeError!                  │
        │  No patient profile exists           │
        │  Triggers 500 error                  │
        └────────────┬─────────────────────────┘
                     │
                     ▼
        ┌──────────────────────────────────────┐
        │  🔴 REGISTRATION FLOW BROKEN         │
        │                                      │
        │  User sees:                          │
        │  ERROR 500                           │
        │  Something went wrong                │
        │                                      │
        │  Cannot proceed                      │
        └──────────────────────────────────────┘
```

### Fixed (With Signal Handler)

```
┌─────────────────────────────────────────────────────────────────────┐
│                     Patient Registration                            │
└─────────────────────────────────────────────────────────────────────┘
                            │
                            ▼
        ┌──────────────────────────────────────┐
        │  User submits registration form      │
        │  username: john_doe                  │
        │  email: john@example.com             │
        │  password: secret123                 │
        └────────────┬─────────────────────────┘
                     │
                     ▼
        ┌──────────────────────────────────────┐
        │  Django creates User object          │
        │  Triggers: post_save signal          │
        └────────────┬─────────────────────────┘
                     │
                     ▼
        ┌──────────────────────────────────────┐
        │  ✓ SIGNAL HANDLER REGISTERED [FIXED] │
        │                                      │
        │  accounts/signals.py: EXISTS         │
        │  accounts/apps.py: ready() method    │
        │  Signal handler listening...         │
        └────────────┬─────────────────────────┘
                     │
                     ▼ @receiver(post_save, sender=User)
        ┌──────────────────────────────────────┐
        │  create_patient_profile():           │
        │  if created and not is_staff:        │
        │    Patient.objects.create()          │
        └────────────┬─────────────────────────┘
                     │
                     ▼
        ┌──────────────────────────────────────┐
        │  ✓ Patient profile created!          │
        │  Database state:                     │
        │                                      │
        │  ✓ User table:                       │
        │    id=1, username=john_doe           │
        │                                      │
        │  ✓ Patient table:                    │
        │    id=1, user_id=1, phone=null...    │
        └────────────┬─────────────────────────┘
                     │
                     ▼
        ┌──────────────────────────────────────┐
        │  User logs in successfully           │
        │  Clicks "Book Appointment"           │
        │  Calls: Book_appointment.get()       │
        │  Accesses: request.user.patient      │
        │                                      │
        │  ✓ Patient profile exists            │
        │  ✓ Can continue                      │
        └────────────┬─────────────────────────┘
                     │
                     ▼
        ┌──────────────────────────────────────┐
        │  ✓ REGISTRATION FLOW WORKING         │
        │                                      │
        │  User successfully proceeds          │
        │  No errors                           │
        │  Can book appointments               │
        └──────────────────────────────────────┘
```

---

## 🔴 BILL NUMBER GENERATION (RACE CONDITION)

### Current (Broken)

```
REQUEST A                          REQUEST B
┌──────────────────┐               ┌──────────────────┐
│ Create Bill      │               │ Create Bill      │
│                  │               │                  │
│ SELECT id FROM   │               │ SELECT id FROM   │
│ bill WHERE id    │─ Time 1.0ms ─→│ bill WHERE id    │
│ max = 3          │               │ max = 3          │
│                  │               │                  │
│ next = 3 + 1 = 4 │               │ next = 3 + 1 = 4 │
│                  │               │                  │
│ Save BILL-0004   │ Time 2.0ms    │ Save BILL-0004   │
│ INSERT OK ✓      │────────────────│ INSERT OK ✓      │
│                  │               │                  │
│ RESULT: Both     │               │ DUPLICATE!       │
│ got BILL-0004    │               │                  │
└──────────────────┘               └──────────────────┘

🔴 Two bills with same bill_number!
   Breaks accounting integrity
```

### Fixed (Atomic)

```
REQUEST A                          REQUEST B
┌──────────────────┐               ┌──────────────────┐
│ Create Bill      │               │ Create Bill      │
│ BEGIN TRANSACTION│               │ (waits)          │
│                  │               │                  │
│ SELECT COUNT     │               │                  │
│ from bill = 3    │───RM Lock────→│ WAITING          │
│                  │               │ For table lock   │
│ next = 3 + 1 = 4 │               │                  │
│                  │               │                  │
│ Save BILL-0004   │               │                  │
│ COMMIT           │               │                  │
│ Release lock ✓   │               │                  │
│                  │               ▼                  │
│                  │      BEGIN TRANSACTION           │
│                  │      SELECT COUNT = 4            │
│                  │      next = 4 + 1 = 5            │
│                  │      Save BILL-0005              │
│                  │      COMMIT ✓                    │
│                  │                                  │
│ Result: Sequential                                  │
│ BILL-0004                                           │
│ BILL-0005                                           │
│ ✓ No duplicates                                     │
└──────────────────────────────────────────────────────┘
```

---

## 📋 Database State Consistency

### Stock Tracking (Current - Broken)

```
Prescription Item: Aspirin 500mg
dose = "1-2", days = 10
qty_needed = (1+2) * 10 = 30 tablets

Medicine Variant:
id=5
name=Aspirin 500mg
stock=100
cost_price=5
selling_price=10

Bill Generated:
- BillItem created (qty=30, price=₹300) ✓
- should_deduct=True (flag set)
- was_deducted=False (❌ NEVER UPDATED)
- Stock in database: STILL 100 ❌

Result:
System shows: 100 tablets in stock
Clinic has: 70 tablets left
Difference: 30 tablets missing!
```

### Fixed Version

```
Prescription Item: Aspirin 500mg
dose = "1-2", days = 10
qty_needed = (1+2) * 10 = 30 tablets

Medicine Variant:
id=5
name=Aspirin 500mg
stock=100
cost_price=5
selling_price=10

Bill Generation (in transaction):
- BillItem created (qty=30, price=₹300) ✓
- Stock updated: 100 - 30 = 70 ✓
- should_deduct=True ✓
- was_deducted=True ✓
- Stock in database: 70 ✓

Result:
System shows: 70 tablets in stock
Clinic has: 70 tablets
✓ Difference: 0 (Consistent!)
```

---

## 🎯 Impact Summary Table

| Issue | Impact | Users Affected | Data Loss | Severity |
|-------|--------|---|---|---|
| Double booking | Overbooking | Patients | No | 🔴 HIGH |
| Patient signal | Registration broken | All new users | Yes | 🔴 HIGH |
| Bill numbers | Accounting wrong | Billers | Yes | 🔴 HIGH |
| Stock not deducted | Inventory wrong | All | Yes | 🟠 MEDIUM |
| No transaction | Partial bills | Billers | Yes | 🟠 MEDIUM |
| Leave incomplete | Wrong slots | Doctors | No | 🟠 MEDIUM |

---

## 🛠️ Testing Flows

To test and verify fixes, use these Python snippets:

### Test 1: Patient Signal
```python
from django.contrib.auth.models import User
from accounts.models import Patient

# Create user
u = User.objects.create_user('testuser', 'test@test.com', 'pass')

# Check patient created
p = Patient.objects.get(user=u)
print(f"✓ Patient signal working: {p}")
```

### Test 2: Bill Numbers Sequential
```python
from billing.models import Bill
from appointment.models import Visit

# Create 3 bills
v = Visit.objects.first()
b1 = Bill.objects.create(visit=v, subtotal=100)
b2 = Bill.objects.create(visit=v, subtotal=200)
b3 = Bill.objects.create(visit=v, subtotal=300)

# Verify sequential
assert b1.bill_number == 'BILL-0001'
assert b2.bill_number == 'BILL-0002'
assert b3.bill_number == 'BILL-0003'
print("✓ Bill numbers sequential")
```

### Test 3: Stock Deduction
```python
from medicine.models import MedicineVariant

v = MedicineVariant.objects.first()
initial = v.stock

# Generate bill (should deduct stock)
# ... create prescription and bill ...

final = v.stock
assert final < initial, "Stock should decrease"
print(f"✓ Stock deducted: {initial} → {final}")
```

### Test 4: Double Booking Prevention
```python
from appointment.models import Appointment
from django.utils import timezone
from datetime import date

doc = InnerMember.objects.first()
pat = Patient.objects.first()

# Try to create 2 appointments at same slot
try:
    a1 = Appointment.objects.create(
        patient=pat, doctor=doc,
        appointment_date=date.today(),
        time_slot='10:00',
        status='pending'
    )
    a2 = Appointment.objects.create(
        patient=pat, doctor=doc,
        appointment_date=date.today(),
        time_slot='10:00',
        status='pending'
    )
    print("❌ Double booking allowed!")
except Exception as e:
    print(f"✓ Double booking prevented: {e}")
```

---

## 📞 Questions to Ask Before Deploying

1. **Data Migration:** Are there existing bills? Need to fix bill_number sequence
2. **Stock History:** Should we track historical stock, not just current?
3. **Notifications:** When appointment slot fills, notify doctor?
4. **Slots Per Doctor:** Each doctor has their own slots or clinic-wide?
5. **Partial Bookings:** Allow booking if doctor partially on leave?
