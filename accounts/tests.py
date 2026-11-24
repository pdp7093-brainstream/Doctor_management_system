from django.test import TestCase
from django.test import override_settings
from django.utils import timezone
from datetime import timedelta
from unittest.mock import patch
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from django.contrib.auth.models import User
from django.contrib.messages import get_messages
from django.http import HttpResponse
from django.test import RequestFactory
from django.core import signing
from django.core.cache import cache
from accounts.models import Patient, PatientFeedback
import time
from accounts.middleware import RoleRedirectMiddleware
from doctor.models import InnerMember
from doctor.hashid import encode_id
from accounts.tokens import patient_invite_token_generator
from accounts.services.patient_import import (
    clean_phone,
    clean_date,
    parse_import_file,
    validate_patient_rows,
    create_patients_from_rows,
)


class ChangePasswordViewTests(TestCase):
    def setUp(self):
        owner = User.objects.create_user(username='setup-owner', password='pass')
        InnerMember.objects.create(user=owner, role='doctor', is_owner=True)

    def test_successful_password_change_redirects_to_profile_and_authenticates_new_password(self):
        user = User.objects.create_user(username='password-change-user', password='OldPassword123!')
        Patient.objects.get_or_create(user=user)
        self.client.force_login(user)

        response = self.client.post(reverse('resetpass'), {
            'old_password': 'OldPassword123!',
            'new_password': 'NewPassword456!',
            'confirm_password': 'NewPassword456!',
        })

        self.assertRedirects(response, reverse('profile'), fetch_redirect_response=False)
        self.assertTrue(self.client.login(username='password-change-user', password='NewPassword456!'))


class RoleRedirectMiddlewareTests(TestCase):
    def setUp(self):
        self.patient_user = User.objects.create_user(username='role-patient', password='pass')
        Patient.objects.get_or_create(user=self.patient_user)
        self.staff_user = User.objects.create_user(username='role-staff', password='pass')
        InnerMember.objects.create(user=self.staff_user, role='doctor', is_owner=True)

    def test_patient_login_redirects_to_dashboard(self):
        self.client.force_login(self.patient_user)
        response = self.client.get('/login/')
        self.assertRedirects(response, reverse('dashboard'), fetch_redirect_response=False)

    def test_patient_doctor_dashboard_redirects_to_patient_dashboard(self):
        self.client.force_login(self.patient_user)
        response = self.client.get('/doctor/dashboard/')
        self.assertRedirects(response, reverse('dashboard'), fetch_redirect_response=False)

    def test_staff_login_redirects_to_doctor_dashboard(self):
        self.client.force_login(self.staff_user)
        response = self.client.get('/login/')
        self.assertRedirects(response, reverse('doctor:dashboard'), fetch_redirect_response=False)

    def test_staff_redirects_from_patient_only_pages(self):
        staff_admin = User.objects.create_user(
            username='role-staff-admin', password='pass', is_staff=True,
        )
        patient_only_paths = (
            '/user-profile/', '/profile-setting/', '/appointment/',
            '/appointment/appointment/example/', '/add-family-member/',
            '/upload-profile-document/',
        )
        for user in (self.staff_user, staff_admin):
            self.client.force_login(user)
            for path in patient_only_paths:
                with self.subTest(username=user.username, path=path):
                    response = self.client.get(path)
                    self.assertRedirects(
                        response, reverse('doctor:dashboard'), fetch_redirect_response=False,
                    )

    def test_staff_can_open_public_pages(self):
        factory = RequestFactory()
        middleware = RoleRedirectMiddleware(lambda request: HttpResponse('passed'))
        for path in ('/', '/about/', '/treatments/', '/feedback/'):
            with self.subTest(path=path):
                request = factory.get(path)
                request.user = self.staff_user
                self.assertEqual(middleware(request).content, b'passed')

    def test_anonymous_login_shows_patient_login_page(self):
        response = self.client.get('/login/')
        self.assertEqual(response.status_code, 200)

    def test_static_and_ajax_requests_pass_through(self):
        factory = RequestFactory()
        middleware = RoleRedirectMiddleware(lambda request: HttpResponse('passed'))
        static_request = factory.get('/static/example.css')
        static_request.user = self.patient_user
        ajax_request = factory.get('/doctor/dashboard/', HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        ajax_request.user = self.patient_user
        self.assertEqual(middleware(static_request).content, b'passed')
        self.assertEqual(middleware(ajax_request).content, b'passed')


class ProfilePhoneUpdateTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='profile-phone-user', password='pass')
        self.patient, _ = Patient.objects.get_or_create(user=self.user)
        owner = User.objects.create_user(username='profile-phone-owner', password='pass')
        InnerMember.objects.create(user=owner, role='doctor', is_owner=True)
        self.client.force_login(self.user)

    def post_profile(self, phone):
        return self.client.post(reverse('profile-setting'), {
            'full_name': 'Profile Phone User',
            'phone': phone,
        })

    def test_phone_requires_exactly_ten_ascii_digits(self):
        for phone in ('123456789', '12345678901', '12345abc90', '+1234567890'):
            with self.subTest(phone=phone):
                response = self.post_profile(phone)
                self.assertEqual(response.status_code, 302)
                errors = [message.message for message in get_messages(response.wsgi_request)]
                self.assertIn('Phone number must contain exactly 10 digits.', errors)
                self.patient.refresh_from_db()
                self.assertIsNone(self.patient.phone)

    def test_duplicate_phone_shows_requested_error(self):
        other_user = User.objects.create_user(username='existing-phone-user', password='pass')
        other_patient, _ = Patient.objects.get_or_create(user=other_user)
        other_patient.phone = '9876543210'
        other_patient.save()

        response = self.post_profile('9876543210')
        errors = [message.message for message in get_messages(response.wsgi_request)]

        self.assertIn('This number is already registered', errors)
        self.patient.refresh_from_db()
        self.assertIsNone(self.patient.phone)

    def test_empty_phone_is_saved_as_null(self):
        self.patient.phone = '9876543210'
        self.patient.save()

        response = self.post_profile('')

        self.assertRedirects(response, reverse('profile'), fetch_redirect_response=False)
        self.patient.refresh_from_db()
        self.assertIsNone(self.patient.phone)

    def test_valid_phone_is_saved(self):
        response = self.post_profile('0123456789')

        self.assertRedirects(response, reverse('profile'), fetch_redirect_response=False)
        self.patient.refresh_from_db()
        self.assertEqual(self.patient.phone, '0123456789')


class PatientImportTests(TestCase):
    def test_phone_cleaning_and_validation(self):
        # Valid cases: 10 digits directly, with +91, with leading 0, with dashes/spaces
        phone, err = clean_phone("9876543210")
        self.assertEqual(phone, "9876543210")
        self.assertEqual(err, "")

        phone, err = clean_phone("+91 98765-43210")
        self.assertEqual(phone, "9876543210")
        self.assertEqual(err, "")

        phone, err = clean_phone("09876543210")
        self.assertEqual(phone, "9876543210")
        self.assertEqual(err, "")

        phone, err = clean_phone("98765 43210")
        self.assertEqual(phone, "9876543210")
        self.assertEqual(err, "")

        # Invalid cases
        phone, err = clean_phone("12345")
        self.assertEqual(phone, "")
        self.assertTrue("must be 10 digits" in err)

        phone, err = clean_phone("abcdefghij")
        self.assertEqual(phone, "")
        self.assertTrue("must be 10 digits" in err)

        phone, err = clean_phone("")
        self.assertEqual(phone, "")
        self.assertEqual(err, "")

    def test_name_only_patient_import_sets_null_and_skips_reupload(self):
        rows = [{"_row_num": 2, "name": "Name Only Patient", "phone": ""}]

        validated = validate_patient_rows(rows)
        self.assertEqual(validated[0]["status"], "New")
        self.assertEqual(validated[0]["reason"], "Ready (no phone)")

        first_import = create_patients_from_rows(validated)
        self.assertEqual(first_import["created_count"], 1)
        patient = Patient.objects.get(user__first_name="Name", user__last_name="Only Patient")
        self.assertIsNone(patient.phone)

        revalidated = validate_patient_rows(rows)
        self.assertEqual(revalidated[0]["status"], "Duplicate")
        self.assertEqual(revalidated[0]["reason"], "Duplicate (same name, no phone)")

        second_import = create_patients_from_rows(revalidated)
        self.assertEqual(second_import["created_count"], 0)
        self.assertEqual(second_import["duplicate_count"], 1)
        self.assertEqual(Patient.objects.filter(user__first_name="Name", user__last_name="Only Patient").count(), 1)

    def test_same_name_with_different_case_numbers_imports_both(self):
        rows = [
            {"_row_num": 2, "name": "Same Name Patient", "phone": "", "case_no": "REG-100"},
            {"_row_num": 3, "name": "Same Name Patient", "phone": "", "case_no": "REG-101"},
        ]

        validated = validate_patient_rows(rows)
        self.assertEqual([row["status"] for row in validated], ["New", "New"])
        result = create_patients_from_rows(validated)

        self.assertEqual(result["created_count"], 2)
        self.assertEqual(
            set(Patient.objects.filter(user__first_name="Same", user__last_name="Name Patient").values_list("case_no", flat=True)),
            {"REG-100", "REG-101"},
        )

    def test_same_case_number_is_skipped_in_file_and_against_database(self):
        existing_user = User.objects.create_user(username="case-existing", first_name="Existing")
        existing_user.patient.case_no = "DB-200"
        existing_user.patient.save(update_fields=["case_no"])
        rows = [
            {"_row_num": 2, "name": "File One", "case_no": "FILE-100"},
            {"_row_num": 3, "name": "File Two", "case_no": " file-100 "},
            {"_row_num": 4, "name": "Database Existing", "case_no": " db-200 "},
        ]

        validated = validate_patient_rows(rows)
        self.assertEqual([row["status"] for row in validated], ["New", "Duplicate", "Duplicate"])
        result = create_patients_from_rows(validated)
        self.assertEqual(result["created_count"], 1)
        self.assertEqual(result["duplicate_count"], 2)
        self.assertEqual(Patient.objects.get(user__first_name="File").case_no, "FILE-100")

    def test_case_number_column_aliases_are_normalized(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        for header in ("case_no", "old_register_no", "register_no"):
            with self.subTest(header=header):
                uploaded = SimpleUploadedFile(
                    "patients.csv",
                    f"name,{header}\nAlias Patient,ALIAS-300\n".encode(),
                )
                parsed = parse_import_file(uploaded)
                self.assertEqual(parsed[0]["case_no"], "ALIAS-300")

    def test_three_date_formats(self):
        # dd/mm/yyyy
        d1, err1 = clean_date("15/08/1990")
        self.assertEqual(d1, "1990-08-15")
        self.assertEqual(err1, "")

        # dd-mm-yyyy
        d2, err2 = clean_date("26-01-1985")
        self.assertEqual(d2, "1985-01-26")
        self.assertEqual(err2, "")

        # yyyy-mm-dd
        d3, err3 = clean_date("2000-12-31")
        self.assertEqual(d3, "2000-12-31")
        self.assertEqual(err3, "")

        # Invalid date
        d_bad, err_bad = clean_date("31/02/2020")
        self.assertEqual(d_bad, "")
        self.assertTrue("Invalid date" in err_bad)

    def test_valid_row_with_and_without_email(self):
        rows = [
            {
                "_row_num": 2,
                "name": "Rohan Gupta",
                "phone": "+91 9876543210",
                "email": "rohan@example.com",
                "gender": "male",
                "dob": "15/08/1990",
                "blood_group": "B+",
                "address": "Delhi, India",
            },
            {
                "_row_num": 3,
                "name": "Sneha Sharma",
                "phone": "9123456789",
                "email": "",
                "gender": "Female",
                "dob": "1995-05-20",
                "blood_group": "o+",
                "address": "Mumbai",
            },
        ]

        validated = validate_patient_rows(rows)
        self.assertEqual(len(validated), 2)
        self.assertEqual(validated[0]["status"], "New")
        self.assertEqual(validated[1]["status"], "New")

        results = create_patients_from_rows(validated, dry_run=False)
        self.assertEqual(results["created_count"], 2)
        self.assertEqual(results["duplicate_count"], 0)
        self.assertEqual(results["error_count"], 0)

        # Verify database records
        # Row 1 (with email): username should be rohan@example.com
        user1 = User.objects.get(username="rohan@example.com")
        self.assertEqual(user1.email, "rohan@example.com")
        self.assertEqual(user1.first_name, "Rohan")
        self.assertEqual(user1.last_name, "Gupta")
        self.assertTrue(hasattr(user1, "patient"))
        self.assertEqual(user1.patient.phone, "9876543210")
        self.assertEqual(user1.patient.gender, "Male")
        self.assertEqual(user1.patient.bld_grop, "B+")
        self.assertEqual(str(user1.patient.dob), "1990-08-15")

        # Row 2 (without email): username should be pt-9123456789
        user2 = User.objects.get(username="pt-9123456789")
        self.assertEqual(user2.email, "")
        self.assertEqual(user2.first_name, "Sneha")
        self.assertEqual(user2.last_name, "Sharma")
        self.assertEqual(user2.patient.phone, "9123456789")
        self.assertEqual(user2.patient.gender, "Female")
        self.assertEqual(user2.patient.bld_grop, "O+")

        self.assertEqual(str(user2.patient.dob), "1995-05-20")

    def test_duplicate_phone_in_database(self):
        # Create an existing patient
        user = User.objects.create_user(username="existing", email="existing@example.com")
        patient = user.patient
        patient.phone = "9988776655"
        patient.save()

        rows = [
            {
                "_row_num": 2,
                "name": "Duplicate Tester",
                "phone": "9988776655",
                "email": "different@example.com",
            }
        ]

        validated = validate_patient_rows(rows)
        self.assertEqual(len(validated), 1)
        self.assertEqual(validated[0]["status"], "Duplicate")
        self.assertTrue("already exists" in validated[0]["reason"])

        # Attempt to create should skip it
        results = create_patients_from_rows(validated, dry_run=False)
        self.assertEqual(results["created_count"], 0)
        self.assertEqual(results["duplicate_count"], 1)

    def test_duplicate_inside_file(self):
        rows = [
            {
                "_row_num": 2,
                "name": "Patient One",
                "phone": "9811223344",
                "email": "test1@example.com",
            },
            {
                "_row_num": 3,
                "name": "Patient Two (Same Phone)",
                "phone": "9811223344",
                "email": "test2@example.com",
            },
            {
                "_row_num": 4,
                "name": "Patient Three (Same Email)",
                "phone": "9877001122",
                "email": "test1@example.com",
            },
        ]

        validated = validate_patient_rows(rows)
        self.assertEqual(validated[0]["status"], "New")
        self.assertEqual(validated[1]["status"], "Duplicate")
        self.assertTrue("multiple times" in validated[1]["reason"])
        self.assertEqual(validated[2]["status"], "Duplicate")
        self.assertTrue("multiple times" in validated[2]["reason"])

    def test_invalid_phone_and_missing_name(self):
        rows = [
            {
                "_row_num": 2,
                "name": "",
                "phone": "123",
            }
        ]

        validated = validate_patient_rows(rows)
        self.assertEqual(validated[0]["status"], "Error")
        self.assertTrue("Missing name" in validated[0]["reason"])
        self.assertTrue("10 digits" in validated[0]["reason"])


class PatientInviteTests(TestCase):
    def setUp(self):
        self.doctor = User.objects.create_user(username='doctor-test', password='doctor-pass')
        InnerMember.objects.create(user=self.doctor, role='doctor', is_owner=True)
        self.patient_user = User.objects.create_user(username='invitee@example.com', email='invitee@example.com')
        self.patient_user.set_unusable_password()
        self.patient_user.save()
        self.patient = self.patient_user.patient
        self.client.force_login(self.doctor)

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend', DEFAULT_FROM_EMAIL='clinic@example.com')
    def test_invite_sets_timestamp_and_sends_one_email(self):
        response = self.client.post(reverse('doctor:send_patient_invite', args=[encode_id(self.patient.pk)]))
        self.assertEqual(response.status_code, 302)
        self.patient.refresh_from_db()
        self.assertIsNotNone(self.patient.invite_sent_at)
        from django.core import mail
        self.assertEqual(len(mail.outbox), 1)

    def test_invite_token_becomes_invalid_after_password_set(self):
        token = patient_invite_token_generator.make_token(self.patient_user)
        self.assertTrue(patient_invite_token_generator.check_token(self.patient_user, token))
        self.patient_user.set_password('NewStrongPass99!')
        self.patient_user.save()
        self.assertFalse(patient_invite_token_generator.check_token(self.patient_user, token))

    def test_invite_token_expires_after_48_hours(self):
        token = patient_invite_token_generator.make_token(self.patient_user)
        future = timezone.now() + timedelta(hours=49)
        with patch.object(patient_invite_token_generator, '_now', return_value=future):
            self.assertFalse(patient_invite_token_generator.check_token(self.patient_user, token))

    def test_staff_cannot_change_active_patient_email(self):
        self.patient_user.set_password('KnownPass123!')
        self.patient_user.save()
        response = self.client.post(reverse('doctor:edit_patient', args=[encode_id(self.patient.pk)]), {
            'name': 'Patient Name', 'email': 'changed@example.com', 'phone': '', 'case_no': 'INV-001',
        })
        self.assertEqual(response.status_code, 302)
        self.patient_user.refresh_from_db()
        self.assertEqual(self.patient_user.email, 'invitee@example.com')

    def test_staff_can_change_non_active_patient_email(self):
        response = self.client.post(reverse('doctor:edit_patient', args=[encode_id(self.patient.pk)]), {
            'name': 'Patient Name', 'email': 'changed@example.com', 'phone': '', 'case_no': 'INV-001',
        })
        self.assertEqual(response.status_code, 302)
        self.patient_user.refresh_from_db()
        self.assertEqual(self.patient_user.email, 'changed@example.com')

    def test_adding_email_to_legacy_patient_invalidates_existing_password(self):
        self.patient_user.email = ''
        self.patient_user.set_password('LegacyKnownPassword123!')
        self.patient_user.save()

        response = self.client.post(reverse('doctor:edit_patient', args=[encode_id(self.patient.pk)]), {
            'name': 'Patient Name',
            'email': 'legacy@example.com',
            'phone': '',
            'case_no': 'LEGACY-001',
        })

        self.assertEqual(response.status_code, 302)
        self.patient_user.refresh_from_db()
        self.patient.refresh_from_db()
        self.assertFalse(self.patient_user.has_usable_password())
        self.assertEqual(self.patient.login_status, 'none')

    def test_adding_email_and_inviting_legacy_patient_invalidates_password(self):
        self.patient_user.email = ''
        self.patient_user.set_password('LegacyKnownPassword123!')
        self.patient_user.save()

        with patch('accounts.services.invites.EmailMultiAlternatives') as email_message:
            email_message.return_value.send.return_value = 1
            response = self.client.post(reverse('doctor:edit_patient', args=[encode_id(self.patient.pk)]), {
                'name': 'Patient Name',
                'email': 'legacy-invite@example.com',
                'phone': '',
                'case_no': 'LEGACY-002',
                'send_login_invite': 'on',
            })

        self.assertEqual(response.status_code, 302)
        self.patient_user.refresh_from_db()
        self.patient.refresh_from_db()
        self.assertFalse(self.patient_user.has_usable_password())
        self.assertEqual(self.patient.login_status, 'invited')

    def test_usable_password_without_email_has_no_login_status(self):
        self.patient_user.email = ''
        self.patient_user.set_password('KnownPass123!')
        self.patient_user.save()
        self.assertEqual(self.patient.login_status, 'none')

    def test_activation_page_sets_password_and_consumes_token(self):
        token = patient_invite_token_generator.make_token(self.patient_user)
        uidb64 = urlsafe_base64_encode(force_bytes(self.patient_user.pk))
        url = reverse('activate_patient', args=[uidb64, token])
        response = self.client.post(url, {'new_password1': 'StrongPass123!xyz', 'new_password2': 'StrongPass123!xyz'})
        self.assertEqual(response.status_code, 302)
        self.patient_user.refresh_from_db()
        self.assertTrue(self.patient_user.has_usable_password())
        self.assertFalse(patient_invite_token_generator.check_token(self.patient_user, token))

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend', DEFAULT_FROM_EMAIL='clinic@example.com')
    def test_forgot_password_sends_reset_for_imported_patient(self):
        response = self.client.post(reverse('password_reset'), {'email': self.patient_user.email})
        self.assertEqual(response.status_code, 302)
        from django.core import mail
        self.assertEqual(len(mail.outbox), 1)


class PublicFeedbackProtectionTests(TestCase):
    def setUp(self):
        cache.clear()
        owner = User.objects.create_user(username='feedback-test-owner', password='pass')
        InnerMember.objects.create(user=owner, role='doctor', is_owner=True)

    def feedback_payload(self, **overrides):
        from accounts.views import FEEDBACK_FORM_SIGNING_SALT

        payload = {
            'name': 'Feedback User',
            'email': 'feedback@example.com',
            'phone': '',
            'rating': '5',
            'message': 'This is useful feedback.',
            'feedback_timestamp': signing.dumps(time.time() - 4, salt=FEEDBACK_FORM_SIGNING_SALT),
        }
        payload.update(overrides)
        return payload

    def test_honeypot_submission_silently_succeeds_without_saving(self):
        response = self.client.post(
            reverse('feedback'),
            self.feedback_payload(website='spam'),
            REMOTE_ADDR='192.0.2.10',
        )

        self.assertRedirects(response, reverse('feedback'), fetch_redirect_response=False)
        self.assertEqual(PatientFeedback.objects.count(), 0)
        self.assertIn(
            'Thank you for your feedback! We truly appreciate it.',
            [message.message for message in get_messages(response.wsgi_request)],
        )

    def test_feedback_rate_limit_rejects_submission_after_three(self):
        for _ in range(3):
            response = self.client.post(
                reverse('feedback'),
                self.feedback_payload(),
                REMOTE_ADDR='192.0.2.11',
            )
            self.assertEqual(response.status_code, 302)

        response = self.client.post(
            reverse('feedback'),
            self.feedback_payload(),
            REMOTE_ADDR='192.0.2.11',
        )

        self.assertEqual(response.status_code, 302)
        self.assertIn(
            'Too many submissions, please try again later.',
            [message.message for message in get_messages(response.wsgi_request)],
        )
        self.assertEqual(PatientFeedback.objects.count(), 3)


class CaseNoTests(TestCase):
    def setUp(self):
        self.doctor_user = User.objects.create_user(username='caseno-doctor', password='pass')
        InnerMember.objects.create(user=self.doctor_user, role='doctor', is_owner=True)
        self.client.force_login(self.doctor_user)

        # A patient with a case_no
        self.user1 = User.objects.create_user(
            username='caseno-patient1@example.com',
            email='caseno-patient1@example.com',
            first_name='Ravi', last_name='Kumar',
        )
        self.patient1 = self.user1.patient
        self.patient1.case_no = '1194'
        self.patient1.save()

        # A patient without case_no
        self.user2 = User.objects.create_user(
            username='caseno-patient2@example.com',
            email='caseno-patient2@example.com',
            first_name='Meena', last_name='Sharma',
        )
        self.patient2 = self.user2.patient

    def test_case_no_saved_on_patient(self):
        self.patient1.refresh_from_db()
        self.assertEqual(self.patient1.case_no, '1194')

    def test_edit_patient_invite_status_is_saved_before_send_and_shown_after_redirect(self):
        def assert_invite_status_saved_before_send(*args, **kwargs):
            self.patient1.refresh_from_db()
            self.assertEqual(self.patient1.login_status, 'invited')
            return 1

        with patch('accounts.services.invites.EmailMultiAlternatives') as email_message:
            email_message.return_value.send.side_effect = assert_invite_status_saved_before_send
            response = self.client.post(
                reverse('doctor:edit_patient', args=[encode_id(self.patient1.pk)]),
                {
                    'name': 'Ravi Kumar',
                    'email': 'caseno-patient1@example.com',
                    'phone': '',
                    'case_no': '1194',
                    'send_login_invite': 'on',
                },
            )

        self.assertRedirects(response, reverse('doctor:manage_patients'), fetch_redirect_response=False)
        list_response = self.client.get(reverse('doctor:manage_patients'))
        self.assertEqual(list_response.status_code, 200)
        self.assertIn('no-store', list_response.headers['Cache-Control'])
        patient_row = next(
            row for row in list_response.context['patients'].object_list
            if row['id'] == self.patient1.pk
        )
        self.assertEqual(patient_row['login_status'], 'invited')
        self.assertContains(list_response, 'Invited ·')

    def test_edit_forms_prefill_existing_case_numbers(self):
        patient_response = self.client.get(
            reverse('doctor:edit_patient', args=[encode_id(self.patient1.pk)]),
        )
        self.assertEqual(patient_response.status_code, 200)
        self.assertContains(patient_response, 'id="patient-case-no" type="text" name="case_no" class="form-control" value="1194"')

        from accounts.models import FamilyMember
        member = FamilyMember.objects.create(
            patient=self.patient1,
            name='Sita Kumar',
            relation='Wife',
            case_no='9999',
        )
        family_response = self.client.get(
            reverse('doctor:edit_family', args=[encode_id(member.pk)]),
        )
        self.assertEqual(family_response.status_code, 200)
        self.assertContains(family_response, 'id="family-case-no" type="text" name="case_no" class="form-control" value="9999"')

    def test_case_no_search_finds_patient_in_manage_patients(self):
        response = self.client.get(reverse('doctor:manage_patients'), {'search': '1194'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Ravi')

    def test_case_no_search_finds_family_member_in_manage_patients(self):
        from accounts.models import FamilyMember
        member = FamilyMember.objects.create(
            patient=self.patient1,
            name='Sita Kumar',
            relation='Wife',
            case_no='9999',
        )
        response = self.client.get(reverse('doctor:manage_patients'), {'search': '9999'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Sita Kumar')

    def test_duplicate_case_no_is_rejected(self):
        # Edit patient2 to use a whitespace-padded, case-insensitive duplicate.
        self.patient1.case_no = 'AbC-1194'
        self.patient1.save(update_fields=['case_no'])
        response = self.client.post(
            reverse('doctor:edit_patient', args=[encode_id(self.patient2.pk)]),
            {
                'name': 'Meena Sharma',
                'email': 'caseno-patient2@example.com',
                'phone': '',
                'case_no': ' abc-1194 ',
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Case No. abc-1194 is already used by Ravi Kumar')
        self.assertContains(response, 'value=" abc-1194 "')
        self.assertEqual(response.context['case_no_error'], 'Case No. abc-1194 is already used by Ravi Kumar (—)')
        self.patient2.refresh_from_db()
        self.assertEqual(self.patient2.case_no, '')

    def test_family_duplicate_name_and_relation_shows_error(self):
        from accounts.models import FamilyMember

        FamilyMember.objects.create(
            patient=self.patient1,
            name='Sita Kumar',
            relation='Wife',
            case_no='FAM-100',
        )
        response = self.client.post(reverse('doctor:add_patient'), {
            'name': 'Sita Kumar',
            'parent_patient': str(self.patient1.pk),
            'relation': 'Wife',
            'case_no': 'FAM-101',
        })

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            'A family member with this name and relation already exists for this patient.',
        )
        self.assertEqual(FamilyMember.objects.filter(patient=self.patient1).count(), 1)

    def test_add_patient_without_email_creates_no_login_and_sends_no_email(self):
        with patch('doctor.views.send_welcome_email') as send_welcome:
            response = self.client.post(reverse('doctor:add_patient'), {
                'name': 'No Email Patient',
                'email': '',
                'phone': '',
                'case_no': 'NO-EMAIL-100',
            })

        self.assertEqual(response.status_code, 302)
        patient = Patient.objects.get(case_no='NO-EMAIL-100')
        self.assertEqual(patient.user.email, '')
        self.assertTrue(patient.user.username.startswith('pt-'))
        self.assertFalse(patient.user.has_usable_password())
        self.assertEqual(patient.login_status, 'none')
        send_welcome.assert_not_called()
        self.assertIn('Patient added.', [m.message for m in get_messages(response.wsgi_request)])

    def test_add_patient_with_email_keeps_email_flow(self):
        with patch('doctor.views.send_welcome_email') as send_welcome:
            response = self.client.post(reverse('doctor:add_patient'), {
                'name': 'Email Patient',
                'email': 'email-patient@example.com',
                'phone': '',
                'case_no': 'EMAIL-100',
            })

        self.assertEqual(response.status_code, 302)
        patient = Patient.objects.get(case_no='EMAIL-100')
        self.assertEqual(patient.user.email, 'email-patient@example.com')
        self.assertEqual(patient.user.username, 'email-patient@example.com')
        send_welcome.assert_called_once()

    def test_case_no_is_required_for_doctor_patient_and_family_forms(self):
        from accounts.models import FamilyMember

        add_patient_response = self.client.post(reverse('doctor:add_patient'), {
            'name': 'New Patient',
            'email': 'new-case-required@example.com',
            'case_no': '   ',
        })
        self.assertEqual(add_patient_response.status_code, 200)
        self.assertContains(add_patient_response, 'Case No. is required.')
        self.assertFalse(User.objects.filter(username='new-case-required@example.com').exists())

        edit_patient_response = self.client.post(
            reverse('doctor:edit_patient', args=[encode_id(self.patient2.pk)]),
            {'name': 'Meena Sharma', 'email': 'caseno-patient2@example.com', 'case_no': ''},
        )
        self.assertEqual(edit_patient_response.status_code, 200)
        self.assertContains(edit_patient_response, 'Case No. is required.')
        self.patient2.refresh_from_db()
        self.assertEqual(self.patient2.case_no, '')

        family_count = FamilyMember.objects.count()
        add_family_response = self.client.post(reverse('doctor:add_patient'), {
            'name': 'New Family Member',
            'parent_patient': str(self.patient1.pk),
            'relation': 'Other',
            'case_no': ' ',
        })
        self.assertEqual(add_family_response.status_code, 200)
        self.assertContains(add_family_response, 'Case No. is required.')
        self.assertEqual(FamilyMember.objects.count(), family_count)

        member = FamilyMember.objects.create(
            patient=self.patient1,
            name='Existing Family Member',
            relation='Other',
            case_no='FM-100',
        )
        edit_family_response = self.client.post(
            reverse('doctor:edit_family', args=[encode_id(member.pk)]),
            {'name': member.name, 'relation': member.relation, 'case_no': ''},
        )
        self.assertEqual(edit_family_response.status_code, 200)
        self.assertContains(edit_family_response, 'Case No. is required.')
        member.refresh_from_db()
        self.assertEqual(member.case_no, 'FM-100')

    def test_inline_case_no_update_succeeds(self):
        response = self.client.post(
            reverse('doctor:update_case_no', args=['main', encode_id(self.patient2.pk)]),
            {'case_no': ' 264 '},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'ok': True, 'case_no': '264'})
        self.patient2.refresh_from_db()
        self.assertEqual(self.patient2.case_no, '264')

    def test_inline_case_no_update_rejects_empty_value(self):
        response = self.client.post(
            reverse('doctor:update_case_no', args=['main', encode_id(self.patient2.pk)]),
            {'case_no': '  '},
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), {'ok': False, 'error': 'Case No. is required.'})
        self.patient2.refresh_from_db()
        self.assertEqual(self.patient2.case_no, '')

    def test_inline_case_no_update_rejects_duplicate(self):
        response = self.client.post(
            reverse('doctor:update_case_no', args=['main', encode_id(self.patient2.pk)]),
            {'case_no': '1194'},
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), {
            'ok': False,
            'error': 'Case No. 1194 is already used by Ravi Kumar (—)',
        })
        self.patient2.refresh_from_db()
        self.assertEqual(self.patient2.case_no, '')

    def test_inline_case_no_update_for_non_staff_returns_403(self):
        non_staff = User.objects.create_user(username='case-no-non-staff', password='pass')
        self.client.force_login(non_staff)
        response = self.client.post(
            reverse('doctor:update_case_no', args=['main', encode_id(self.patient2.pk)]),
            {'case_no': '264'},
        )
        self.assertEqual(response.status_code, 403)
        self.patient2.refresh_from_db()
        self.assertEqual(self.patient2.case_no, '')


class ImportCaseNumbersTests(TestCase):
    def setUp(self):
        import openpyxl  # noqa
        from accounts.models import FamilyMember
        self.report_path = "test_case_numbers_report.csv"
        self.temp_files = []
        self.user1 = User.objects.create_user(
            username="single-match@example.com",
            first_name="Ravi",
            last_name="Verma",
        )
        self.patient1 = self.user1.patient
        self.patient1.case_no = ""
        self.patient1.save()

    def tearDown(self):
        import os
        if os.path.exists(self.report_path):
            os.remove(self.report_path)
        if os.path.exists("report.csv"):
            os.remove("report.csv")
        for f in self.temp_files:
            if os.path.exists(f):
                os.remove(f)

    def _create_xlsx(self, rows, headers=("name", "old_register_no", "check_note", "page")):
        import tempfile
        import openpyxl
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(list(headers))
        for r in rows:
            ws.append(list(r))
        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
            temp_path = f.name
            wb.save(temp_path)
        self.temp_files.append(temp_path)
        return temp_path

    def test_single_match_sets_case_no(self):
        from django.core.management import call_command
        xlsx = self._create_xlsx([
            ["Ravi Verma", "1194", "", "1"],
        ])
        call_command("import_case_numbers", xlsx, "--apply", f"--report={self.report_path}")
        self.patient1.refresh_from_db()
        self.assertEqual(self.patient1.case_no, "1194")

    def test_duplicate_names_skipped(self):
        from django.core.management import call_command
        # Create second patient with the exact same name
        user2 = User.objects.create_user(
            username="another-ravi@example.com",
            first_name="Ravi",
            last_name="Verma",
        )
        patient2 = user2.patient
        patient2.case_no = ""
        patient2.save()

        xlsx = self._create_xlsx([
            ["Ravi Verma", "2222", "", "1"],
        ])
        call_command("import_case_numbers", xlsx, "--apply", f"--report={self.report_path}")
        self.patient1.refresh_from_db()
        patient2.refresh_from_db()
        self.assertEqual(self.patient1.case_no, "")
        self.assertEqual(patient2.case_no, "")

    def test_existing_case_no_not_overwritten(self):
        from django.core.management import call_command
        self.patient1.case_no = "100"
        self.patient1.save()

        xlsx = self._create_xlsx([
            ["Ravi Verma", "200", "", "1"],
        ])
        call_command("import_case_numbers", xlsx, "--apply", f"--report={self.report_path}")
        self.patient1.refresh_from_db()
        self.assertEqual(self.patient1.case_no, "100")

    def test_row_with_check_note_skipped(self):
        from django.core.management import call_command
        xlsx = self._create_xlsx([
            ["Ravi Verma", "3333", "Verify name spelling", "2"],
        ])
        call_command("import_case_numbers", xlsx, "--apply", f"--report={self.report_path}")
        self.patient1.refresh_from_db()
        self.assertEqual(self.patient1.case_no, "")

    def test_dry_run_changes_nothing(self):
        from django.core.management import call_command
        xlsx = self._create_xlsx([
            ["Ravi Verma", "4444", "", "3"],
        ])
        call_command("import_case_numbers", xlsx, f"--report={self.report_path}")
        self.patient1.refresh_from_db()
        self.assertEqual(self.patient1.case_no, "")

    def test_multi_number_value_saved_as_is(self):
        from django.core.management import call_command
        xlsx = self._create_xlsx([
            ["Ravi Verma", "1691 / 1745", "", "4"],
        ])
        call_command("import_case_numbers", xlsx, "--apply", f"--report={self.report_path}")
        self.patient1.refresh_from_db()
        self.assertEqual(self.patient1.case_no, "1691 / 1745")

    def test_family_member_single_match_sets_case_no(self):
        from django.core.management import call_command
        from accounts.models import FamilyMember
        member = FamilyMember.objects.create(
            patient=self.patient1,
            name="Aarti Verma",
            relation="Wife",
            case_no="",
        )
        xlsx = self._create_xlsx([
            ["Aarti Verma", "5555", "", "5"],
        ])
        call_command("import_case_numbers", xlsx, "--apply", f"--report={self.report_path}")
        member.refresh_from_db()
        self.assertEqual(member.case_no, "5555")

    def test_accepts_case_no_header_alternative(self):
        from django.core.management import call_command
        xlsx = self._create_xlsx(
            [["Ravi Verma", "7777", "", "6"]],
            headers=("name", "case_no", "check_note", "page"),
        )
        call_command("import_case_numbers", xlsx, "--apply", f"--report={self.report_path}")
        self.patient1.refresh_from_db()
        self.assertEqual(self.patient1.case_no, "7777")

    def test_check_note_same_name_appears_ignored(self):
        import csv
        from django.core.management import call_command
        xlsx = self._create_xlsx([
            ["Ravi Verma", "8888", "same name appears 2 times", "7"],
        ])
        call_command("import_case_numbers", xlsx, "--apply", f"--report={self.report_path}")
        self.patient1.refresh_from_db()
        self.assertEqual(self.patient1.case_no, "8888")

        # Verify original check note is kept in report.csv
        with open(self.report_path, "r", encoding="utf-8") as f:
            reader = list(csv.DictReader(f))
            self.assertEqual(len(reader), 1)
            self.assertEqual(reader[0]["status"], "will set")
            self.assertEqual(reader[0]["check_note"], "same name appears 2 times")

    def test_check_note_mixed_retains_needs_check(self):
        from django.core.management import call_command
        xlsx = self._create_xlsx([
            ["Ravi Verma", "8889", "same name appears 2 times; verify spelling", "8"],
        ])
        call_command("import_case_numbers", xlsx, "--apply", f"--report={self.report_path}")
        self.patient1.refresh_from_db()
        self.assertEqual(self.patient1.case_no, "")

    def test_duplicate_in_register_not_set(self):
        import csv
        from django.core.management import call_command
        xlsx = self._create_xlsx([
            ["Ravi Verma", "9001", "", "9"],
            ["  ravi   verma  ", "9002", "", "10"],
        ])
        call_command("import_case_numbers", xlsx, "--apply", f"--report={self.report_path}")
        self.patient1.refresh_from_db()
        self.assertEqual(self.patient1.case_no, "")

        with open(self.report_path, "r", encoding="utf-8") as f:
            reader = list(csv.DictReader(f))
            self.assertEqual(len(reader), 2)
            self.assertEqual(reader[0]["status"], "duplicate in register")
            self.assertEqual(reader[1]["status"], "duplicate in register")

    def test_edit_patient_can_remove_email_and_sends_no_invite(self):
        with patch('accounts.services.invites.send_patient_invite_email') as send_invite:
            response = self.client.post(
                reverse('doctor:edit_patient', args=[encode_id(self.patient1.pk)]),
                {
                    'name': 'Ravi Kumar',
                    'email': '',
                    'phone': '',
                    'case_no': '1194',
                    'send_login_invite': 'on',
                },
            )

        self.assertEqual(response.status_code, 302)
        self.user1.refresh_from_db()
        self.patient1.refresh_from_db()
        self.assertEqual(self.user1.email, '')
        send_invite.assert_not_called()


