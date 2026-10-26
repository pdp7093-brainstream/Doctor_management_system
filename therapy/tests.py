from datetime import time
from decimal import Decimal

from django.contrib.auth.models import User
from django.contrib.messages.storage.fallback import FallbackStorage
from django.http import QueryDict
from django.test import RequestFactory, TestCase
from django.urls import reverse
from django.utils import timezone

from appointment.models import Appointment, Prescription, Visit
from .models import PrescriptionTherapy, Therapy
from .views import TherapyDeleteView
from appointment.views import parse_prescription_therapies, save_prescription_therapies


class TherapyTests(TestCase):
    def test_seed_therapies_exist_in_requested_order(self):
        therapies = list(Therapy.objects.all())
        self.assertEqual(
            [(therapy.name, therapy.duration_minutes) for therapy in therapies],
            [
                ('Abhyanga', 60),
                ('Shirodhara', 45),
                ('Swedana', 20),
                ('Nasya', 20),
                ('Basti', 45),
                ('Kati Basti', 30),
                ('Janu Basti', 30),
                ('Udvartana', 45),
                ('Pizhichil', 60),
                ('Virechana', 45),
            ],
        )
        self.assertTrue(all(therapy.is_active and therapy.price_per_session == 0 for therapy in therapies))

    def setUp(self):
        patient_user = User.objects.create_user(username='therapy-patient')
        from accounts.models import Patient
        patient = Patient.objects.get(user=patient_user)
        doctor_user = User.objects.create_user(username='therapy-doctor')
        from doctor.models import InnerMember
        doctor = InnerMember.objects.create(user=doctor_user, role='doctor')
        appointment = Appointment.objects.create(
            patient=patient,
            doctor=doctor,
            appointment_date=timezone.localdate(),
            time_slot=time(11, 0),
        )
        visit = Visit.objects.create(patient=patient, doctor=doctor, appointment=appointment)
        self.prescription = Prescription.objects.create(visit=visit)

    def test_used_therapy_cannot_be_deleted(self):
        therapy = Therapy.objects.create(name='Therapy used by patient')
        PrescriptionTherapy.objects.create(prescription=self.prescription, therapy=therapy)
        user = User.objects.create_user(username='therapy-panel-user')
        request = RequestFactory().post(
            reverse('doctor:therapy:therapy_delete', args=[therapy.pk])
        )
        request.user = user
        request.session = {}
        request._messages = FallbackStorage(request)
        response = TherapyDeleteView().post(request, pk=therapy.pk)

        self.assertTrue(Therapy.objects.filter(pk=therapy.pk).exists())
        self.assertEqual(response.status_code, 302)
        self.assertIn(
            'Used in 1 prescriptions. Deactivate it instead.',
            str(list(request._messages)[0]),
        )

    def test_removing_one_row_preserves_the_other_prescribed_therapy(self):
        first = Therapy.objects.create(name='First therapy', price_per_session='25.00')
        second = Therapy.objects.create(name='Second therapy', price_per_session='40.00')
        data = QueryDict('', mutable=True)
        data.setlist('therapy_id[]', [str(first.pk), str(second.pk)])
        data.setlist('therapy_item_id[]', ['', ''])
        data.setlist('therapy_sessions[]', ['4', '8'])
        data.setlist('therapy_frequency[]', ['daily', 'weekly'])
        data.setlist('therapy_start[]', ['', ''])
        data.setlist('therapy_notes[]', ['first notes', 'second notes'])

        rows, error = parse_prescription_therapies(data, self.prescription)
        self.assertIsNone(error)
        save_prescription_therapies(self.prescription, rows)
        second_row = self.prescription.therapies.get(therapy=second)
        self.assertEqual(second_row.price_per_session, Decimal('40.00'))

        data.setlist('therapy_id[]', [str(second.pk)])
        data.setlist('therapy_item_id[]', [str(second_row.pk)])
        data.setlist('therapy_sessions[]', ['9'])
        data.setlist('therapy_frequency[]', ['alternate'])
        data.setlist('therapy_start[]', [''])
        data.setlist('therapy_notes[]', ['kept row'])
        rows, error = parse_prescription_therapies(data, self.prescription)
        self.assertIsNone(error)
        save_prescription_therapies(self.prescription, rows)

        remaining = list(self.prescription.therapies.select_related('therapy'))
        self.assertEqual(len(remaining), 1)
        self.assertEqual(remaining[0].pk, second_row.pk)
        self.assertEqual(remaining[0].therapy, second)
        self.assertEqual(remaining[0].sessions, 9)
        self.assertEqual(remaining[0].frequency, 'alternate')