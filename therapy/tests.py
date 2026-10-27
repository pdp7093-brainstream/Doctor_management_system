from datetime import time
from decimal import Decimal

from django.contrib.auth.models import User
from django.contrib.messages.storage.fallback import FallbackStorage
from django.http import QueryDict
from django.test import RequestFactory, TestCase
from django.urls import reverse
from django.utils import timezone

from appointment.models import Appointment, Prescription, Visit
from billing.models import Bill
from billing.views import generate_bill_from_visit
from .models import PrescriptionTherapy, Therapy, TherapyBillItem, TherapySession
from .views import TherapyDeleteView
from appointment.views import parse_prescription_therapies, save_prescription_therapies


class TherapyTests(TestCase):
    def test_therapy_sessions_list_accepts_get(self):
        self.client.force_login(self.doctor_user)
        response = self.client.get(reverse('doctor:therapy:therapy_sessions'))
        self.assertEqual(response.status_code, 200)

    def test_record_session_post_redirects_back_with_query(self):
        prescribed = self.make_prescribed_therapy()
        self.client.force_login(self.doctor_user)
        list_url = reverse('doctor:therapy:therapy_sessions')
        response = self.client.post(
            reverse('doctor:therapy:mark_session_done', args=[prescribed.pk]),
            {
                'date': timezone.localdate().isoformat(),
                'status': 'done',
                'return_to': list_url,
                'return_query': 'search=patient&status=active&page=2',
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], f'{list_url}?search=patient&status=active&page=2')
        self.assertEqual(prescribed.session_records.count(), 1)

    def test_record_session_url_rejects_get(self):
        prescribed = self.make_prescribed_therapy()
        self.client.force_login(self.doctor_user)
        response = self.client.get(reverse(
            'doctor:therapy:mark_session_done', args=[prescribed.pk]
        ))
        self.assertEqual(response.status_code, 405)

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
        doctor = InnerMember.objects.create(user=doctor_user, role='doctor', is_owner=True)
        self.doctor_user = doctor_user
        appointment = Appointment.objects.create(
            patient=patient,
            doctor=doctor,
            appointment_date=timezone.localdate(),
            time_slot=time(11, 0),
        )
        visit = Visit.objects.create(patient=patient, doctor=doctor, appointment=appointment)
        self.visit = visit
        self.prescription = Prescription.objects.create(visit=visit)

    def make_prescribed_therapy(self, **overrides):
        therapy = overrides.pop('therapy', None)
        if not therapy:
            name = overrides.pop('therapy_name', f'Test billing therapy {Therapy.objects.count() + 1}')
            therapy = Therapy.objects.create(
                name=name,
                default_billing_type='per_session',
                session_price=Decimal('15.00'),
                package_price=Decimal('90.00'),
                default_sessions=3,
            )
        values = {
            'prescription': self.prescription,
            'therapy': therapy,
            'billing_type': 'per_session',
            'total_sessions': 3,
            'session_price': Decimal('15.00'),
            'package_price': Decimal('90.00'),
        }
        values.update(overrides)
        return PrescriptionTherapy.objects.create(**values)

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
        data.setlist('therapy_billing_type[]', ['per_session', 'per_session'])
        data.setlist('therapy_session_price[]', ['25.00', '40.00'])
        data.setlist('therapy_package_price[]', ['', ''])

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
        data.setlist('therapy_billing_type[]', ['per_session'])
        data.setlist('therapy_session_price[]', ['40.00'])
        data.setlist('therapy_package_price[]', [''])
        rows, error = parse_prescription_therapies(data, self.prescription)
        self.assertIsNone(error)
        save_prescription_therapies(self.prescription, rows)

        remaining = list(self.prescription.therapies.select_related('therapy'))
        self.assertEqual(len(remaining), 1)
        self.assertEqual(remaining[0].pk, second_row.pk)
        self.assertEqual(remaining[0].therapy, second)
        self.assertEqual(remaining[0].sessions, 9)
        self.assertEqual(remaining[0].frequency, 'alternate')

    def test_package_is_billed_only_once(self):
        prescribed = self.make_prescribed_therapy(billing_type='package')

        first_bill = generate_bill_from_visit(self.visit)
        second_bill = generate_bill_from_visit(self.visit)

        self.assertEqual(first_bill.pk, second_bill.pk)
        self.assertEqual(Bill.objects.filter(visit=self.visit).count(), 1)
        self.assertEqual(TherapyBillItem.objects.filter(
            prescription_therapy=prescribed, billing_type='package'
        ).count(), 1)
        line = TherapyBillItem.objects.get(prescription_therapy=prescribed)
        self.assertEqual(line.amount, Decimal('90.00'))
        self.assertEqual(first_bill.subtotal, Decimal('90.00'))

    def test_per_session_bills_only_unbilled_done_sessions(self):
        prescribed = self.make_prescribed_therapy()
        sessions = [
            TherapySession.objects.create(prescription_therapy=prescribed, session_no=number)
            for number in (1, 2)
        ]

        first_bill = generate_bill_from_visit(self.visit)
        for session in sessions:
            session.refresh_from_db()
            self.assertEqual(session.bill_id, first_bill.pk)
        self.assertEqual(first_bill.subtotal, Decimal('30.00'))

        third_session = TherapySession.objects.create(
            prescription_therapy=prescribed,
            session_no=3,
        )
        addon_bill = generate_bill_from_visit(self.visit)
        third_session.refresh_from_db()

        self.assertTrue(addon_bill.is_addon)
        self.assertEqual(third_session.bill_id, addon_bill.pk)
        lines = list(TherapyBillItem.objects.filter(
            prescription_therapy=prescribed
        ).order_by('bill_id'))
        self.assertEqual([line.sessions for line in lines], [2, 1])
        self.assertEqual([line.amount for line in lines], [Decimal('30.00'), Decimal('15.00')])

    def test_marking_session_done_cannot_exceed_total_sessions(self):
        prescribed = self.make_prescribed_therapy(total_sessions=1)
        TherapySession.objects.create(prescription_therapy=prescribed, session_no=1)
        self.client.force_login(self.doctor_user)

        response = self.client.post(reverse(
            'doctor:therapy:mark_session_done', args=[prescribed.pk]
        ), {'date': timezone.localdate().isoformat(), 'status': 'done'})

        self.assertEqual(response.status_code, 302)
        self.assertEqual(prescribed.session_records.filter(status='done').count(), 1)
        self.assertEqual(prescribed.session_records.count(), 1)

    def test_missed_session_does_not_count_toward_progress(self):
        prescribed = self.make_prescribed_therapy(total_sessions=3)
        self.client.force_login(self.doctor_user)

        response = self.client.post(
            reverse('doctor:therapy:mark_session_done', args=[prescribed.pk]),
            {'date': timezone.localdate().isoformat(), 'status': 'missed', 'notes': 'Patient unavailable'},
        )

        prescribed.refresh_from_db()
        missed = prescribed.session_records.get()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(missed.status, TherapySession.STATUS_MISSED)
        self.assertEqual(prescribed.sessions_done, 0)
        self.assertEqual(prescribed.progress_text, '0/3')
        self.assertEqual(prescribed.status, 'active')

    def test_undo_billed_session_is_blocked(self):
        prescribed = self.make_prescribed_therapy()
        session = TherapySession.objects.create(
            prescription_therapy=prescribed, session_no=1, status=TherapySession.STATUS_DONE
        )
        bill = generate_bill_from_visit(self.visit)
        session.refresh_from_db()
        self.client.force_login(self.doctor_user)

        response = self.client.post(reverse(
            'doctor:therapy:undo_session', args=[session.pk]
        ))

        self.assertEqual(response.status_code, 302)
        self.assertTrue(prescribed.session_records.filter(pk=session.pk, bill=bill).exists())

    def test_final_session_marks_therapy_completed(self):
        prescribed = self.make_prescribed_therapy(total_sessions=1)
        self.client.force_login(self.doctor_user)

        response = self.client.post(reverse(
            'doctor:therapy:mark_session_done', args=[prescribed.pk]
        ), {'date': timezone.localdate().isoformat(), 'status': 'done'})

        prescribed.refresh_from_db()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(prescribed.status, 'completed')
        self.assertEqual(prescribed.sessions_done, 1)

    def test_record_session_ajax_done_success(self):
        prescribed = self.make_prescribed_therapy(total_sessions=10)
        self.client.force_login(self.doctor_user)
        response = self.client.post(
            reverse('doctor:therapy:mark_session_done', args=[prescribed.pk]),
            {'date': timezone.localdate().isoformat(), 'status': 'done'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['progress_text'], '1/10')
        self.assertEqual(data['progress_percent'], 10)
        self.assertEqual(data['status'], 'active')
        self.assertEqual(data['next_session_no'], 2)
        self.assertEqual(data['last_session_date'], timezone.localdate().strftime('%d %b %Y'))

    def test_record_session_ajax_missed_preserves_progress(self):
        prescribed = self.make_prescribed_therapy(total_sessions=10)
        self.client.force_login(self.doctor_user)
        response = self.client.post(
            reverse('doctor:therapy:mark_session_done', args=[prescribed.pk]),
            {'date': timezone.localdate().isoformat(), 'status': 'missed'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['progress_text'], '0/10')
        self.assertEqual(data['progress_percent'], 0)
        self.assertEqual(data['status'], 'active')
        self.assertEqual(data['next_session_no'], 2)

    def test_record_session_ajax_future_date_returns_400(self):
        from datetime import timedelta
        prescribed = self.make_prescribed_therapy(total_sessions=10)
        self.client.force_login(self.doctor_user)
        future_date = (timezone.localdate() + timedelta(days=1)).isoformat()
        response = self.client.post(
            reverse('doctor:therapy:mark_session_done', args=[prescribed.pk]),
            {'date': future_date, 'status': 'done'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertIn('Choose a valid session date that is not in the future.', data['error'])

    def test_per_session_bill_only_covers_unbilled_sessions(self):
        prescribed = self.make_prescribed_therapy(total_sessions=5, session_price=Decimal('20.00'))
        self.client.force_login(self.doctor_user)

        # 1. "Save & create bill" in record modal saves session 1 and creates bill for that session
        resp1 = self.client.post(
            reverse('doctor:therapy:mark_session_done', args=[prescribed.pk]),
            {
                'date': timezone.localdate().isoformat(),
                'status': 'done',
                'create_bill': 'true',
                'payment_method': 'upi',
            },
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(resp1.status_code, 200)
        s1 = prescribed.session_records.get(session_no=1)
        self.assertIsNotNone(s1.bill)
        bill1 = s1.bill
        self.assertEqual(bill1.payment_method, 'upi')
        self.assertEqual(bill1.subtotal, Decimal('20.00'))
        self.assertEqual(bill1.total, Decimal('20.00'))
        line1 = bill1.therapy_items.get()
        self.assertEqual(line1.therapy_name, f'{prescribed.therapy.name} · Session 1')
        self.assertEqual(line1.sessions, 1)
        self.assertEqual(line1.amount, Decimal('20.00'))

        # 2. Record session 2 and 3 without billing
        s2 = TherapySession.objects.create(
            prescription_therapy=prescribed, session_no=2, status=TherapySession.STATUS_DONE
        )
        s3 = TherapySession.objects.create(
            prescription_therapy=prescribed, session_no=3, status=TherapySession.STATUS_DONE
        )

        # 3. Bill all unbilled sessions via bill_therapy_sessions
        resp2 = self.client.post(
            reverse('doctor:therapy:bill_therapy_sessions', args=[prescribed.pk]),
            {'payment_method': 'cash'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(resp2.status_code, 200)
        s1.refresh_from_db()
        s2.refresh_from_db()
        s3.refresh_from_db()

        self.assertEqual(s1.bill_id, bill1.pk)  # session 1 not changed
        self.assertIsNotNone(s2.bill)
        self.assertEqual(s2.bill_id, s3.bill_id)
        bill2 = s2.bill
        self.assertNotEqual(bill1.pk, bill2.pk)
        self.assertEqual(bill2.subtotal, Decimal('40.00'))
        self.assertEqual(bill2.total, Decimal('40.00'))
        lines = list(bill2.therapy_items.order_by('id'))
        self.assertEqual(len(lines), 2)
        self.assertEqual(lines[0].therapy_name, f'{prescribed.therapy.name} · Session 2')
        self.assertEqual(lines[1].therapy_name, f'{prescribed.therapy.name} · Session 3')

        # 4. Calling bill_therapy_sessions again when there are 0 unbilled returns 400
        resp3 = self.client.post(
            reverse('doctor:therapy:bill_therapy_sessions', args=[prescribed.pk]),
            {'payment_method': 'cash'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(resp3.status_code, 400)

        # 5. Session 4 is recorded; billing now only covers session 4
        s4 = TherapySession.objects.create(
            prescription_therapy=prescribed, session_no=4, status=TherapySession.STATUS_DONE
        )
        resp4 = self.client.post(
            reverse('doctor:therapy:bill_therapy_sessions', args=[prescribed.pk]),
            {'payment_method': 'card'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(resp4.status_code, 200)
        s4.refresh_from_db()
        bill3 = s4.bill
        self.assertEqual(bill3.subtotal, Decimal('20.00'))
        self.assertEqual(bill3.therapy_items.count(), 1)
        self.assertEqual(bill3.therapy_items.get().therapy_name, f'{prescribed.therapy.name} · Session 4')

    def test_package_billed_once(self):
        prescribed = self.make_prescribed_therapy(
            billing_type='package',
            package_price=Decimal('120.00'),
            total_sessions=4,
        )
        self.client.force_login(self.doctor_user)

        # First billing succeeds
        resp1 = self.client.post(
            reverse('doctor:therapy:bill_therapy_package', args=[prescribed.pk]),
            {'payment_method': 'upi'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(resp1.status_code, 200)
        prescribed.refresh_from_db()
        self.assertIsNotNone(prescribed.package_billed)
        bill = prescribed.package_billed
        self.assertEqual(bill.payment_method, 'upi')
        self.assertEqual(bill.total, Decimal('120.00'))

        item = TherapyBillItem.objects.get(prescription_therapy=prescribed)
        self.assertEqual(item.therapy_name, f'{prescribed.therapy.name} · Package (4 sessions)')
        self.assertEqual(item.billing_type, 'package')
        self.assertEqual(item.sessions, 4)
        self.assertEqual(item.amount, Decimal('120.00'))

        # Second billing attempt is blocked server-side
        resp2 = self.client.post(
            reverse('doctor:therapy:bill_therapy_package', args=[prescribed.pk]),
            {'payment_method': 'cash'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(resp2.status_code, 400)
        self.assertIn('already been billed', resp2.json()['error'])
        self.assertEqual(Bill.objects.filter(visit=self.visit).count(), 1)
        self.assertEqual(TherapyBillItem.objects.filter(prescription_therapy=prescribed).count(), 1)

    def test_appointment_bill_skips_already_billed_therapy(self):
        # 1. Per-session therapy: session 1 billed directly, session 2 unbilled
        per_session_therapy = self.make_prescribed_therapy(
            session_price=Decimal('25.00'), total_sessions=3
        )
        s1 = TherapySession.objects.create(
            prescription_therapy=per_session_therapy, session_no=1, status=TherapySession.STATUS_DONE
        )
        self.client.force_login(self.doctor_user)
        self.client.post(
            reverse('doctor:therapy:bill_therapy_sessions', args=[per_session_therapy.pk]),
            {'payment_method': 'cash'},
        )
        s1.refresh_from_db()
        direct_bill = s1.bill
        self.assertIsNotNone(direct_bill)

        s2 = TherapySession.objects.create(
            prescription_therapy=per_session_therapy, session_no=2, status=TherapySession.STATUS_DONE
        )

        # 2. Package therapy: billed directly
        pkg_therapy = self.make_prescribed_therapy(
            billing_type='package', package_price=Decimal('100.00'), total_sessions=5
        )
        self.client.post(
            reverse('doctor:therapy:bill_therapy_package', args=[pkg_therapy.pk]),
            {'payment_method': 'online'},
        )
        pkg_therapy.refresh_from_db()
        self.assertIsNotNone(pkg_therapy.package_billed)

        # Now generate bill from visit (the appointment billing)
        appt_bill = generate_bill_from_visit(self.visit)
        s2.refresh_from_db()

        # The appointment bill should only have session 2 (1 session x 25.00)
        # It must NOT bill session 1 again, and must NOT bill pkg_therapy again
        appt_therapy_lines = list(appt_bill.therapy_items.all())
        self.assertEqual(len(appt_therapy_lines), 1)
        self.assertEqual(appt_therapy_lines[0].prescription_therapy, per_session_therapy)
        self.assertEqual(appt_therapy_lines[0].sessions, 1)
        self.assertEqual(appt_therapy_lines[0].amount, Decimal('25.00'))
        self.assertEqual(s2.bill_id, appt_bill.pk)
        self.assertEqual(s1.bill_id, direct_bill.pk)

        # Generating bill from visit again does not double-bill
        appt_bill_again = generate_bill_from_visit(self.visit)
        self.assertEqual(appt_bill.pk, appt_bill_again.pk)
        self.assertEqual(TherapyBillItem.objects.filter(prescription_therapy=pkg_therapy).count(), 1)

    def test_filter_panel_default_params_and_billing_type(self):
        self.prescription.visit.patient.user.first_name = 'UniqueSessionPatient'
        self.prescription.visit.patient.user.save()
        per_session_therapy = self.make_prescribed_therapy(
            billing_type='per_session',
            status='active',
            therapy_name='Shirodhara Per Session',
        )
        self.client.force_login(self.doctor_user)
        list_url = reverse('doctor:therapy:therapy_sessions')

        # Active therapy shows on the default list URL with empty params
        response = self.client.get(f'{list_url}?search=&status=active&therapy=&billing_type=')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'UniqueSessionPatient')
        self.assertContains(response, f'id="therapy-row-{per_session_therapy.pk}"')
        self.assertContains(response, 'id="filterToggleBtn"')
        self.assertContains(response, 'id="filterPanel"')

        # Default URL ?search=&status=active also shows the therapy
        resp_default = self.client.get(f'{list_url}?search=&status=active')
        self.assertEqual(resp_default.status_code, 200)
        self.assertContains(resp_default, 'UniqueSessionPatient')
        self.assertContains(resp_default, f'id="therapy-row-{per_session_therapy.pk}"')

        # Applying billing_type=package hides a per-session therapy
        resp_package = self.client.get(f'{list_url}?search=&status=active&therapy=&billing_type=package')
        self.assertEqual(resp_package.status_code, 200)
        self.assertNotContains(resp_package, 'UniqueSessionPatient')
        self.assertNotContains(resp_package, f'id="therapy-row-{per_session_therapy.pk}"')

    def test_remove_therapy_unbilled_deletes(self):
        prescribed = self.make_prescribed_therapy()
        session = TherapySession.objects.create(
            prescription_therapy=prescribed,
            session_no=1,
            date=timezone.localdate(),
            status=TherapySession.STATUS_DONE,
        )
        self.client.force_login(self.doctor_user)
        remove_url = reverse('doctor:therapy:remove_therapy', kwargs={'pk': prescribed.pk})
        return_target = '/doctor/therapies/sessions/?status=active&search=test'

        # GET is not allowed
        get_resp = self.client.get(remove_url)
        self.assertEqual(get_resp.status_code, 405)

        # POST removes therapy and its sessions, keeping query params
        post_resp = self.client.post(remove_url, {'return_to': return_target})
        self.assertRedirects(post_resp, return_target)
        self.assertFalse(PrescriptionTherapy.objects.filter(pk=prescribed.pk).exists())
        self.assertFalse(TherapySession.objects.filter(pk=session.pk).exists())

    def test_remove_therapy_billed_cancels(self):
        prescribed = self.make_prescribed_therapy()
        bill = generate_bill_from_visit(self.visit)
        session = TherapySession.objects.create(
            prescription_therapy=prescribed,
            session_no=1,
            date=timezone.localdate(),
            status=TherapySession.STATUS_DONE,
            bill=bill,
        )
        self.client.force_login(self.doctor_user)
        remove_url = reverse('doctor:therapy:remove_therapy', kwargs={'pk': prescribed.pk})

        post_resp = self.client.post(remove_url, {'return_to': '/doctor/therapies/sessions/?status=all'})
        self.assertRedirects(post_resp, '/doctor/therapies/sessions/?status=all')

        prescribed.refresh_from_db()
        self.assertEqual(prescribed.status, 'cancelled')
        self.assertTrue(TherapySession.objects.filter(pk=session.pk).exists())

    def test_remove_therapy_biller_denied(self):
        from doctor.models import InnerMember
        biller_user = User.objects.create_user(username='therapy-biller')
        InnerMember.objects.create(user=biller_user, role='biller', is_owner=False)
        prescribed = self.make_prescribed_therapy()

        self.client.force_login(biller_user)
        remove_url = reverse('doctor:therapy:remove_therapy', kwargs={'pk': prescribed.pk})
        post_resp = self.client.post(remove_url)
        self.assertRedirects(post_resp, reverse('doctor:therapy:therapy_sessions'))
        self.assertTrue(PrescriptionTherapy.objects.filter(pk=prescribed.pk).exists())

    def test_can_delete_therapy_flag_in_session_list(self):
        unbilled = self.make_prescribed_therapy(status='active', therapy_name='Unbilled Therapy')
        billed = self.make_prescribed_therapy(status='active', therapy_name='Billed Therapy')
        bill = generate_bill_from_visit(self.visit)
        billed.package_billed = bill
        billed.save()

        self.client.force_login(self.doctor_user)
        resp = self.client.get(reverse('doctor:therapy:therapy_sessions'))
        self.assertEqual(resp.status_code, 200)

        rows = {item.pk: item for item in resp.context['therapies']}
        self.assertTrue(rows[unbilled.pk].can_delete_therapy)
        self.assertFalse(rows[billed.pk].can_delete_therapy)




