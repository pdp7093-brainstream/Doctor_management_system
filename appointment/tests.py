import importlib
from datetime import time
from types import SimpleNamespace

from django.contrib.messages import get_messages
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.contrib.auth.models import User
from django.urls import reverse
from django.test import SimpleTestCase, TestCase
from django.template.loader import render_to_string
from django.utils import timezone
from unittest.mock import patch

from .file_validation import clean_original_filename, validate_uploaded_document
from .models import Appointment, Patient, Prescription, PrescriptionItem, Visit
from .views import PrescriptionView
from .views import normalize_advice_lines
from clinic.models import ClinicSettings
from doctor.hashid import encode_id
from doctor.models import InnerMember
from medicine.models import Medicine, MedicineVariant


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


class PrescriptionPostFailureTests(TestCase):
    def setUp(self):
        patient_user = User.objects.create_user(username='post-patient')
        patient, _ = Patient.objects.get_or_create(user=patient_user)
        self.doctor_user = User.objects.create_user(username='post-doctor', password='test-password')
        doctor = InnerMember.objects.create(
            user=self.doctor_user,
            role='doctor',
            is_owner=True,
        )
        appointment = Appointment.objects.create(
            patient=patient,
            doctor=doctor,
            appointment_date=timezone.localdate(),
            time_slot=time(11, 0),
        )
        self.visit = Visit.objects.create(patient=patient, doctor=doctor, appointment=appointment)
        self.prescription = Prescription.objects.create(visit=self.visit)
        medicine = Medicine.objects.create(name='Test medicine', short_name='TEST-POST')
        self.variant = MedicineVariant.objects.create(
            medicine=medicine,
            power='100 mg',
            cost_price=10,
            selling_price=15,
            stock=20,
        )
        self.url = reverse('appointment:prescription', args=[encode_id(self.visit.id)])
        self.client.force_login(self.doctor_user)

    def _post_data(self, **extra):
        data = {
            'symptoms': 'Updated symptoms',
            'diagnosis': 'Updated diagnosis',
            'notes': 'Updated notes',
            'pathya': 'Warm water',
            'apathya': '',
            'vihar': '',
        }
        data.update(extra)
        return data

    def test_bill_failure_rolls_back_completion_and_returns_error(self):
        with patch(
            'appointment.views.generate_bill_from_visit',
            side_effect=RuntimeError('test bill failure'),
        ):
            response = self.client.post(
                self.url,
                self._post_data(complete_visit='1'),
            )

        self.visit.refresh_from_db()
        self.visit.appointment.refresh_from_db()
        self.prescription.refresh_from_db()

        self.assertEqual(self.visit.visted_status, 'in_progress')
        self.assertNotEqual(self.visit.appointment.status, 'completed')
        self.assertIsNone(self.visit.symptoms)
        self.assertEqual(self.prescription.pathya, '')
        self.assertTrue(any(
            'Bill could not be generated: test bill failure' in str(message)
            for message in get_messages(response.wsgi_request)
        ))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, self.url)
        self.assertEqual(
            response.wsgi_request.session[f'prescription_form_data_{self.visit.pk}']['symptoms'],
            ['Updated symptoms'],
        )

    def test_invalid_item_edit_shows_error_and_rolls_back_form_changes(self):
        item = PrescriptionItem.objects.create(
            prescription=self.prescription,
            medicine_variant=self.variant,
            dosage='1-0-0-0 (after_food)',
            days=3,
            notes='Saved notes',
        )

        response = self.client.post(
            self.url,
            self._post_data(
                **{
                    'variant_id[]': [str(self.variant.id)],
                    'item_id[]': [str(item.id + 100000)],
                    'morning': ['2'],
                    'afternoon': ['0'],
                    'evening': ['0'],
                    'night': ['0'],
                    'meal': ['after_food'],
                    'anupana': ['Warm water'],
                    'days': ['5'],
                    'medicine_notes': ['Unsaved notes'],
                }
            ),
        )

        self.visit.refresh_from_db()
        item.refresh_from_db()

        self.assertIsNone(self.visit.symptoms)
        self.assertEqual(item.dosage, '1-0-0-0 (after_food)')
        self.assertEqual(item.notes, 'Saved notes')
        self.assertTrue(any(
            'Test medicine' in str(message) and 'not found or invalid' in str(message)
            for message in get_messages(response.wsgi_request)
        ))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, self.url)
        self.assertEqual(
            response.wsgi_request.session[f'prescription_form_data_{self.visit.pk}']['morning'],
            ['2'],
        )

    def test_addon_bill_failure_is_logged_and_warned(self):
        self.visit.visted_status = 'completed'
        self.visit.save(update_fields=['visted_status'])
        appointment = self.visit.appointment
        appointment.status = 'completed'
        appointment.save(update_fields=['status'])

        with self.assertLogs('appointment.views', level='ERROR') as logs:
            with patch(
                'appointment.views.generate_bill_from_visit',
                side_effect=RuntimeError('test addon failure'),
            ):
                response = self.client.post(self.url, self._post_data())

        self.assertIn('Addon bill generation failed for visit', logs.output[0])
        self.assertEqual(response.status_code, 302)
        self.assertTrue(any(
            'Addon bill could not be generated: test addon failure' in str(message)
            for message in get_messages(response.wsgi_request)
        ))


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
