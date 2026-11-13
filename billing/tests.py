from datetime import date, time
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from accounts.models import Patient
from appointment.models import Appointment, Prescription, PrescriptionItem, Visit
from clinic.models import ClinicSettings
from doctor import hashid
from doctor.models import InnerMember
from medicine.models import Medicine, MedicineVariant
from therapy.models import (
    BILLING_TYPE_PACKAGE,
    BILLING_TYPE_PER_SESSION,
    PrescriptionTherapy,
    Therapy,
    TherapySession,
    TherapyBillItem,
)
from .models import Bill, BillItem
from .views import generate_bill_from_visit


class BillingFlowTests(TestCase):
    def setUp(self):
        ClinicSettings.objects.create(default_gst=Decimal('0'), default_consultation_fee=Decimal('0'))

        self.doctor_user = User.objects.create_user(username='doctor', password='password')
        self.doctor = InnerMember.objects.create(user=self.doctor_user, role='doctor', is_owner=True)
        patient_user = User.objects.create_user(username='patient', password='password')
        self.patient = Patient.objects.get(user=patient_user)
        self.patient.phone = '9876543210'
        self.patient.save(update_fields=['phone'])
        appointment = Appointment.objects.create(
            patient=self.patient,
            doctor=self.doctor,
            appointment_date=date(2026, 1, 2),
            time_slot=time(10, 0),
        )
        self.visit = Visit.objects.create(patient=self.patient, doctor=self.doctor, appointment=appointment)
        self.prescription = Prescription.objects.create(visit=self.visit)

    def add_medicine_item(self, short_name, name, price, dosage='1-2', days=3):
        medicine = Medicine.objects.create(name=name, short_name=short_name)
        variant = MedicineVariant.objects.create(
            medicine=medicine,
            power='10 mg',
            cost_price=Decimal('1.00'),
            selling_price=Decimal(price),
        )
        return PrescriptionItem.objects.create(
            prescription=self.prescription,
            medicine_variant=variant,
            dosage=dosage,
            days=days,
        )

    def test_generates_bill_with_prescription_medicines_and_total(self):
        self.add_medicine_item('med1', 'Medicine One', '2.50', dosage='1-2', days=4)
        self.add_medicine_item('med2', 'Medicine Two', '1.25', dosage='1-0-1', days=2)

        bill = generate_bill_from_visit(self.visit)

        self.assertEqual(bill.items.count(), 2)
        self.assertEqual(bill.subtotal, Decimal('35.00'))
        self.assertEqual(bill.total, Decimal('35.00'))
        self.assertEqual(
            sum(item.total_price for item in bill.items.all()), Decimal('35.00')
        )

    def test_repeat_does_not_duplicate_items_and_new_item_creates_addon(self):
        first_item = self.add_medicine_item('med1', 'Medicine One', '2.00')
        original_bill = generate_bill_from_visit(self.visit)

        repeated_bill = generate_bill_from_visit(self.visit)
        self.assertEqual(repeated_bill, original_bill)
        self.assertEqual(BillItem.objects.filter(bill=original_bill).count(), 1)
        first_item.refresh_from_db()
        self.assertEqual(first_item.bill_id, original_bill.id)

        second_item = self.add_medicine_item('med2', 'Medicine Two', '3.00')
        addon_bill = generate_bill_from_visit(self.visit)

        self.assertTrue(addon_bill.is_addon)
        self.assertEqual(addon_bill.parent_bill, original_bill)
        self.assertEqual(addon_bill.items.count(), 1)
        self.assertEqual(addon_bill.items.get().medicine_variant, second_item.medicine_variant)
        self.assertEqual(BillItem.objects.count(), 2)

    def test_therapy_package_once_and_per_session_only_unbilled_done_sessions(self):
        package_therapy = Therapy.objects.create(name='Package Therapy')
        session_therapy = Therapy.objects.create(name='Session Therapy')
        package = PrescriptionTherapy.objects.create(
            prescription=self.prescription,
            therapy=package_therapy,
            billing_type=BILLING_TYPE_PACKAGE,
            total_sessions=5,
            package_price=Decimal('100.00'),
        )
        per_session = PrescriptionTherapy.objects.create(
            prescription=self.prescription,
            therapy=session_therapy,
            billing_type=BILLING_TYPE_PER_SESSION,
            total_sessions=4,
            session_price=Decimal('25.00'),
        )
        first_done = TherapySession.objects.create(prescription_therapy=per_session, session_no=1)
        TherapySession.objects.create(
            prescription_therapy=per_session,
            session_no=2,
            status=TherapySession.STATUS_MISSED,
        )

        first_bill = generate_bill_from_visit(self.visit)

        first_done.refresh_from_db()
        package_line = TherapyBillItem.objects.get(prescription_therapy=package)
        session_line = TherapyBillItem.objects.get(prescription_therapy=per_session)
        self.assertEqual(package_line.amount, Decimal('100.00'))
        self.assertEqual(package_line.sessions, 5)
        self.assertEqual(session_line.sessions, 1)
        self.assertEqual(session_line.amount, Decimal('25.00'))
        self.assertEqual(first_done.bill, first_bill)

        second_done = TherapySession.objects.create(prescription_therapy=per_session, session_no=3)
        addon_bill = generate_bill_from_visit(self.visit)

        self.assertTrue(addon_bill.is_addon)
        self.assertEqual(TherapyBillItem.objects.filter(prescription_therapy=package).count(), 1)
        self.assertEqual(TherapyBillItem.objects.filter(prescription_therapy=per_session).count(), 2)
        self.assertEqual(TherapyBillItem.objects.get(bill=addon_bill).sessions, 1)
        second_done.refresh_from_db()
        self.assertEqual(second_done.bill, addon_bill)
        self.assertEqual(
            list(TherapyBillItem.objects.filter(prescription_therapy=per_session).values_list('amount', flat=True)),
            [Decimal('25.00'), Decimal('25.00')],
        )

    def test_bill_detail_is_available_to_doctor_and_blocked_for_patient(self):
        self.add_medicine_item('med1', 'Medicine One', '2.00')
        url = reverse('billing:bill_detail', kwargs={'hid': hashid.encode_id(self.visit.id)})

        self.client.force_login(self.doctor_user)
        self.assertEqual(self.client.get(url).status_code, 200)

        self.client.force_login(self.patient.user)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, '/dashboard/')
        self.assertNotIn('Medicine One', response.content.decode())
