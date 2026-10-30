import importlib
from datetime import time
from types import SimpleNamespace

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase
from django.template.loader import render_to_string
from django.utils import timezone

from .file_validation import clean_original_filename, validate_uploaded_document
from .models import Appointment, Patient, Prescription, PrescriptionItem, Visit
from .views import PrescriptionView
from .views import normalize_advice_lines
from clinic.models import ClinicSettings


class UploadedDocumentValidationTests(SimpleTestCase):
    def test_accepts_pdf_and_sanitizes_name(self):
        uploaded_file = SimpleUploadedFile("../report.pdf", b"%PDF-1.4\ncontent")

        self.assertEqual(validate_uploaded_document(uploaded_file), "report.pdf")
        self.assertEqual(clean_original_filename("../report.pdf"), "report.pdf")

    def test_rejects_executable_content(self):
        uploaded_file = SimpleUploadedFile("report.pdf", b"MZ executable content")

        with self.assertRaisesMessage(ValidationError, "Executable files are not allowed"):
            validate_uploaded_document(uploaded_file)

    def test_rejects_content_type_mismatch(self):
        uploaded_file = SimpleUploadedFile("report.pdf", b"plain text content")

        with self.assertRaisesMessage(ValidationError, "File content does not match"):
            validate_uploaded_document(uploaded_file)


class PrescriptionItemTests(TestCase):
    def test_anupana_is_saved(self):
        patient_user = User.objects.create_user(username='prescription-patient')
        patient, _ = Patient.objects.get_or_create(user=patient_user)
        doctor_user = User.objects.create_user(username='prescription-doctor')
        from doctor.models import InnerMember
        doctor = InnerMember.objects.create(user=doctor_user, role='doctor')
        appointment = Appointment.objects.create(
            patient=patient,
            doctor=doctor,
            appointment_date=timezone.localdate(),
            time_slot=time(9, 0),
        )
        visit = Visit.objects.create(patient=patient, doctor=doctor, appointment=appointment)
        prescription = Prescription.objects.create(visit=visit)

        item = PrescriptionItem.objects.create(
            prescription=prescription,
            dosage='1-0-1-0 (after_food)',
            sevan_kaal='after_food',
            anupana='Warm Water',
            days=3,
        )

        item.refresh_from_db()
        self.assertEqual(item.anupana, 'Warm Water')

    def test_empty_stomach_dosage_parses_and_quantity_is_unchanged(self):
        parsed = PrescriptionView().parse_dosage('1-0-1-0 (empty_stomach)')

        self.assertEqual(parsed, (1, 0, 1, 0, 'empty_stomach'))
        dose_parts = [int(part) for part in '1-0-1-0 (empty_stomach)'.split(' (')[0].split('-')]
        self.assertEqual(sum(dose_parts) * 7, 14)


class PrescriptionAdviceTests(TestCase):
    def setUp(self):
        patient_user = User.objects.create_user(username='advice-patient', first_name='Test')
        patient, _ = Patient.objects.get_or_create(user=patient_user)
        doctor_user = User.objects.create_user(username='advice-doctor')
        from doctor.models import InnerMember
        doctor = InnerMember.objects.create(user=doctor_user, role='doctor')
        appointment = Appointment.objects.create(
            patient=patient,
            doctor=doctor,
            appointment_date=timezone.localdate(),
            time_slot=time(10, 0),
        )
        self.visit = Visit.objects.create(patient=patient, doctor=doctor, appointment=appointment)
        self.prescription = Prescription.objects.create(visit=self.visit)

    def test_advice_lines_are_normalized_and_saved(self):
        self.prescription.pathya = normalize_advice_lines(' Warm water \n\nMOONG DAL\nwarm water ')
        self.prescription.apathya = normalize_advice_lines('Fried food\nfried FOOD\nLate eating')
        self.prescription.save()
        self.prescription.refresh_from_db()

        self.assertEqual(self.prescription.pathya, 'Warm water\nMOONG DAL')
        self.assertEqual(self.prescription.pathya_list, ['Warm water', 'MOONG DAL'])
        self.assertEqual(self.prescription.apathya, 'Fried food\nLate eating')
        self.assertEqual(self.prescription.apathya_list, ['Fried food', 'Late eating'])

    def test_empty_advice_values_stay_empty(self):
        self.prescription.pathya = normalize_advice_lines('')
        self.prescription.apathya = normalize_advice_lines('None')
        self.prescription.vihar = ''
        self.prescription.save()
        self.prescription.refresh_from_db()

        self.assertEqual(self.prescription.pathya, '')
        self.assertEqual(self.prescription.apathya, '')
        self.assertEqual(self.prescription.vihar, '')

    def test_print_page_renders_with_and_without_advice(self):
        context = {
            'visit': self.visit,
            'prescription': self.prescription,
            'prescription_items': [],
            'clinic': ClinicSettings.get(),
            'default_doctor': None,
        }
        without_advice = render_to_string('appointment/prescription_print.html', context)
        self.assertNotIn('Pathya – Take', without_advice)

        self.prescription.pathya = 'Warm water'
        self.prescription.apathya = 'Fried food'
        self.prescription.vihar = 'Walk daily'
        self.prescription.save()
        context['prescription'] = self.prescription
        with_advice = render_to_string('appointment/prescription_print.html', context)
        self.assertIn('Pathya – Take', with_advice)
        self.assertIn('Apathya – Avoid', with_advice)
        self.assertIn('Walk daily', with_advice)


class SevanKaalDataMigrationTests(SimpleTestCase):
    def test_maps_existing_dosage_keys_and_leaves_unknown_blank(self):
        migration = importlib.import_module(
            'appointment.migrations.0024_prescriptionitem_anupana_prescriptionitem_sevan_kaal'
        )
        items = [
            SimpleNamespace(dosage='1-0-1-0 (after_food)', sevan_kaal=''),
            SimpleNamespace(dosage='1-0-0-0 (empty_stomach)', sevan_kaal=''),
            SimpleNamespace(dosage='1-0-0-0 (unknown)', sevan_kaal=''),
            SimpleNamespace(dosage='1-0-0-0', sevan_kaal=''),
        ]

        class ItemManager:
            def all(self):
                return self

            def iterator(self):
                return iter(items)

            def bulk_update(self, updated_items, fields):
                self.updated_items = updated_items
                self.updated_fields = fields

        manager = ItemManager()
        historical_model = SimpleNamespace(objects=manager)
        apps = SimpleNamespace(get_model=lambda *args: historical_model)

        migration.populate_sevan_kaal(apps, None)

        self.assertEqual([item.sevan_kaal for item in items], [
            'after_food', 'empty_stomach', '', '',
        ])
        self.assertEqual(manager.updated_items, items[:2])
        self.assertEqual(manager.updated_fields, ['sevan_kaal'])
