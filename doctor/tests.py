from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from django.utils import timezone
from doctor.models import InnerMember
from accounts.models import Patient, FamilyMember


class ManagePatientsFilterTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.doctor_user = User.objects.create_user(
            username='doctor_test',
            password='password123',
            first_name='Dr',
            last_name='Who',
        )
        InnerMember.objects.create(
            user=self.doctor_user,
            role='doctor',
            is_owner=True,
        )
        Patient.objects.filter(user=self.doctor_user).delete()
        self.client.force_login(self.doctor_user)

        # Patient 1: Active password, male, has phone, name starts with 'A'
        self.u1 = User.objects.create_user(
            username='alice_user',
            password='usablepassword',
            first_name='Alice',
            last_name='Anderson',
            email='alice@example.com',
        )
        self.p1 = Patient.objects.get(user=self.u1)
        self.p1.phone = '1112223333'
        self.p1.gender = 'female'
        self.p1.save()

        # Patient 2: Unusable password, invited with invite_sent_at, male, no phone, name starts with 'B'
        self.u2 = User.objects.create_user(
            username='bob_user',
            first_name='Bob',
            last_name='Brown',
            email='bob@example.com',
        )
        self.u2.set_unusable_password()
        self.u2.save()
        self.p2 = Patient.objects.get(user=self.u2)
        self.p2.phone = None
        self.p2.gender = 'male'
        self.p2.invite_sent_at = timezone.now()
        self.p2.save()

        # Patient 3: Unusable password, no invite sent, no phone, other gender, name starts with 'C'
        self.u3 = User.objects.create_user(
            username='charlie_user',
            first_name='Charlie',
            last_name='Chaplin',
        )
        self.u3.set_unusable_password()
        self.u3.save()
        self.p3 = Patient.objects.get(user=self.u3)
        self.p3.phone = None
        self.p3.gender = 'other'
        self.p3.save()

        # Family member for p1: no user account, has phone, name starts with 'D'
        self.f1 = FamilyMember.objects.create(
            patient=self.p1,
            name='David Anderson',
            phone='4445556666',
            gender='male',
            relation='Son',
        )

    def test_manage_patients_all(self):
        url = reverse('doctor:manage_patients')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['patients'].object_list), 4)
        self.assertEqual(response.context['active_filter_count'], 0)

    def test_filter_login_status(self):
        url = reverse('doctor:manage_patients')

        # Active
        resp = self.client.get(url, {'login_status': 'active'})
        names = [p['name'] for p in resp.context['patients'].object_list]
        self.assertEqual(names, ['Alice Anderson'])
        self.assertEqual(resp.context['active_filter_count'], 1)

        # Invited
        resp = self.client.get(url, {'login_status': 'invited'})
        names = [p['name'] for p in resp.context['patients'].object_list]
        self.assertEqual(names, ['Bob Brown'])

        # No login (Charlie and David)
        resp = self.client.get(url, {'login_status': 'none'})
        names = [p['name'] for p in resp.context['patients'].object_list]
        self.assertEqual(sorted(names), ['Charlie Chaplin', 'David Anderson'])

    def test_filter_phone(self):
        url = reverse('doctor:manage_patients')

        # Has phone
        resp = self.client.get(url, {'phone': 'has_phone'})
        names = [p['name'] for p in resp.context['patients'].object_list]
        self.assertEqual(sorted(names), ['Alice Anderson', 'David Anderson'])

        # No phone
        resp = self.client.get(url, {'phone': 'no_phone'})
        names = [p['name'] for p in resp.context['patients'].object_list]
        self.assertEqual(sorted(names), ['Bob Brown', 'Charlie Chaplin'])

    def test_filter_gender(self):
        url = reverse('doctor:manage_patients')

        # Male (Bob Brown, David Anderson)
        resp = self.client.get(url, {'gender': 'male'})
        names = [p['name'] for p in resp.context['patients'].object_list]
        self.assertEqual(sorted(names), ['Bob Brown', 'David Anderson'])

        # Female (Alice Anderson)
        resp = self.client.get(url, {'gender': 'female'})
        names = [p['name'] for p in resp.context['patients'].object_list]
        self.assertEqual(names, ['Alice Anderson'])

    def test_filter_letter(self):
        url = reverse('doctor:manage_patients')

        # First letter 'A'
        resp = self.client.get(url, {'letter': 'A'})
        names = [p['name'] for p in resp.context['patients'].object_list]
        self.assertEqual(names, ['Alice Anderson'])

        # First letter 'D'
        resp = self.client.get(url, {'letter': 'D'})
        names = [p['name'] for p in resp.context['patients'].object_list]
        self.assertEqual(names, ['David Anderson'])

    def test_combined_filters_and_pagination_query(self):
        url = reverse('doctor:manage_patients')
        resp = self.client.get(url, {'login_status': 'active', 'gender': 'female', 'letter': 'A'})
        self.assertEqual(resp.context['active_filter_count'], 3)
        self.assertIn('login_status=active', resp.context['pagination_query'])
        self.assertIn('gender=female', resp.context['pagination_query'])
        self.assertIn('letter=A', resp.context['pagination_query'])
        self.assertEqual(len(resp.context['filter_chips']), 3)
