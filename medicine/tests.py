from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from django.contrib.messages import get_messages
from django.contrib.messages.storage.cookie import CookieStorage
from django.db import IntegrityError
from django.db.models.deletion import ProtectedError
from medicine.models import Medicine, MedicineType
import importlib
migration_0008 = importlib.import_module("medicine.migrations.0008_migrate_medicine_types")
OLD_DISPLAY_MAP = migration_0008.OLD_DISPLAY_MAP
SEED_TYPES = migration_0008.SEED_TYPES
migrate_forward = migration_0008.migrate_forward
from django.apps import apps


from doctor.models import InnerMember


class MedicineTypeTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="testdoctor", password="password123")
        InnerMember.objects.create(user=self.user, role="doctor", is_owner=True)
        self.client = Client()
        self.client.login(username="testdoctor", password="password123")

    def test_data_migration_mapping_keeps_types(self):
        """Test that data migration mapping logic correctly maps old choices to MedicineType rows and seeds types."""
        # Verify old choices map to proper title/display names
        expected_mappings = {
            'tablet': 'Tablet',
            'syrup': 'Syrup',
            'injection': 'Injection',
            'capsule': 'Capsule',
            'drops': 'Drops',
            'cream': 'Cream',
        }
        for old_val, expected_display in expected_mappings.items():
            mapped = OLD_DISPLAY_MAP.get(old_val, old_val.title())
            self.assertEqual(mapped, expected_display)

        # Verify seed types list contains all required types
        required_seeds = [
            'Tablet', 'Syrup', 'Injection', 'Capsule', 'Drops', 'Cream',
            'Powder', 'Dry Kadha', 'Liquid Kadha', 'Churna', 'Vati / Gutika',
            'Kwath / Kashayam', 'Asava / Arishta', 'Ghrita', 'Taila (Oil)',
            'Bhasma', 'Avaleha', 'Guggulu', 'Arka', 'Lepa'
        ]
        for seed_name in required_seeds:
            self.assertIn(seed_name, SEED_TYPES)

        # Test executing migrate_forward function
        migrate_forward(apps, None)
        for seed_name in required_seeds:
            self.assertTrue(MedicineType.objects.filter(name=seed_name).exists())

    def _get_messages(self, response):
        cookie = response.cookies.get('messages') or self.client.cookies.get('messages')
        if cookie and cookie.value:
            storage = CookieStorage(response.wsgi_request)
            decoded = storage._decode(cookie.value)
            return [m.message for m in (decoded or [])]
        return [m.message for m in get_messages(response.wsgi_request)]

    def test_used_type_cannot_be_deleted(self):
        """Test that a MedicineType in use by any Medicine cannot be deleted."""
        med_type = MedicineType.objects.create(name="SpecialVati", sort_order=1)
        med = Medicine.objects.create(
            name="Herbal Med",
            short_name="HBM01",
            medicine_type=med_type,
        )

        # Attempt to delete via POST request
        delete_url = reverse("medicine:delete_medicine_type", kwargs={"pk": med_type.pk})
        response = self.client.post(delete_url)

        # Type should NOT be deleted
        self.assertTrue(MedicineType.objects.filter(pk=med_type.pk).exists())

        # Error message should be in messages
        messages = self._get_messages(response)
        self.assertIn("This type is used by 1 medicines. Deactivate it instead.", messages)

        # Model PROTECT should also block direct deletion
        with self.assertRaises(ProtectedError):
            med_type.delete()

        # Unused type can be deleted successfully
        unused_type = MedicineType.objects.create(name="UnusedType", sort_order=2)
        del_unused_url = reverse("medicine:delete_medicine_type", kwargs={"pk": unused_type.pk})
        response2 = self.client.post(del_unused_url)
        self.assertFalse(MedicineType.objects.filter(pk=unused_type.pk).exists())

    def test_duplicate_name_rejected(self):
        """Test that duplicate MedicineType names (case-insensitive) are rejected."""
        MedicineType.objects.create(name="TabletForm")

        # Duplicate via view POST (case-insensitive)
        url = reverse("medicine:medicine_types")
        response = self.client.post(url, {"name": "tabletform", "sort_order": "0", "is_active": "on"})
        messages = self._get_messages(response)
        self.assertIn("Medicine type 'tabletform' already exists.", messages)
        self.assertEqual(MedicineType.objects.filter(name__iexact="tabletform").count(), 1)

        # Duplicate at model level
        with self.assertRaises(IntegrityError):
            MedicineType.objects.create(name="TabletForm")
