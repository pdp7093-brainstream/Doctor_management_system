from io import BytesIO
from unittest.mock import patch

from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from django.contrib.messages import get_messages
from django.contrib.messages.storage.cookie import CookieStorage
from django.db import IntegrityError
from django.db.models.deletion import ProtectedError
from django.core.files.uploadedfile import SimpleUploadedFile
from medicine.models import Medicine, MedicineType, MedicineVariant
from medicine.services.medicine_importer import (
    MissingRequiredHeaders,
    import_medicine_rows,
    parse_medicine_excel,
)
from openpyxl import Workbook
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


class MedicineImporterTests(TestCase):
    def _workbook(self, headers, values):
        workbook = Workbook()
        sheet = workbook.active
        sheet.append(headers)
        sheet.append(values)
        output = BytesIO()
        workbook.save(output)
        workbook.close()
        output.seek(0)
        return output

    def _upload_file(self, headers, values):
        workbook = self._workbook(headers, values)
        return SimpleUploadedFile(
            'medicines.xlsx',
            workbook.getvalue(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )

    def _login_import_user(self):
        user = User.objects.create_user(username='medicine-import-doctor', password='password123')
        InnerMember.objects.create(user=user, role='doctor', is_owner=True)
        self.client.login(username='medicine-import-doctor', password='password123')

    def _row(self, short_name, name=None, packs=3):
        return {
            'row_num': 2,
            'name': name or short_name,
            'short_name': short_name,
            'type': '',
            'company': '',
            'pack_size': '100 gm',
            'unit': 'jar',
            'units_per_pack': 2,
            'cost_price': '10.00',
            'selling_price': '15.00',
            'packs': packs,
            'stock_units': packs * 2,
            'low_stock_alert': 10,
            'mfg_date': '',
            'exp_date': '',
            'status': 'Update existing',
            'reason': '',
        }

    def test_headers_match_aliases_case_insensitively_in_any_order(self):
        workbook = self._workbook(
            [' MANUFACTURER ', 'Code', 'Selling Price', 'Strength', 'Medicine Name', 'COST_PRICE', 'Medicine Type', 'Unit', 'stock_strips', 'unit_per_strip'],
            ['Ayur Care', 'ASH-01', 120, '100 gm', 'Ashwagandha Churna', 80, 'Churna', 'JAR', 5, 1],
        )

        rows = parse_medicine_excel(workbook)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['name'], 'Ashwagandha Churna')
        self.assertEqual(rows[0]['short_name'], 'ASH-01')
        self.assertEqual(rows[0]['pack_size'], '100 gm')
        self.assertEqual(rows[0]['unit'], 'jar')
        self.assertEqual(rows[0]['stock_units'], 5)

    def test_missing_required_header_lists_expected_header_row(self):
        workbook = self._workbook(
            ['name', 'short_name', 'pack_size', 'selling_price'],
            ['Ashwagandha', 'ASH-02', '100 gm', 100],
        )

        with self.assertRaises(MissingRequiredHeaders) as raised:
            parse_medicine_excel(workbook)

        self.assertIn('cost_price', str(raised.exception))
        self.assertIn('Expected header row:', str(raised.exception))

    def test_zero_selling_price_is_rejected_in_preview(self):
        workbook = self._workbook(
            ['name', 'short_name', 'pack_size', 'cost_price', 'selling_price'],
            ['Ashwagandha', 'ASH-03', '100 gm', 50, 0],
        )

        row = parse_medicine_excel(workbook)[0]

        self.assertEqual(row['status'], 'Error')
        self.assertIn('selling price 0', row['reason'])

    def test_blank_units_per_pack_treats_packs_as_stock_units(self):
        workbook = self._workbook(
            ['name', 'short_name', 'pack_size', 'cost_price', 'selling_price', 'packs', 'units_per_pack'],
            ['Ashwagandha', 'ASH-04', '100 gm', 50, 75, 4, None],
        )

        row = parse_medicine_excel(workbook)[0]

        self.assertEqual(row['status'], 'New medicine')
        self.assertIsNone(row['units_per_pack'])
        self.assertEqual(row['stock_units'], 4)

    def test_add_and_replace_stock_options(self):
        medicine = Medicine.objects.create(name='Test medicine', short_name='TEST-01')
        variant = MedicineVariant.objects.create(
            medicine=medicine,
            power='100 gm',
            cost_price=10,
            selling_price=15,
            stock=20,
        )
        row = self._row('TEST-01')

        import_medicine_rows([row], 'add')
        variant.refresh_from_db()
        self.assertEqual(variant.stock, 26)
        import_medicine_rows([row], 'replace')
        variant.refresh_from_db()
        self.assertEqual(variant.stock, 6)
        import_medicine_rows([row], 'keep')
        variant.refresh_from_db()
        self.assertEqual(variant.stock, 6)

    def test_one_database_error_does_not_rollback_other_rows(self):
        first_row = self._row('ISOLATE-01')
        second_row = self._row('ISOLATE-02')
        actual_create = MedicineVariant.objects.create
        call_count = 0

        def fail_first_create(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError('simulated row failure')
            return actual_create(**kwargs)

        with patch('medicine.services.medicine_importer.MedicineVariant.objects.create', side_effect=fail_first_create):
            result = import_medicine_rows([first_row, second_row], 'add')

        self.assertEqual(result['success_count'], 1)
        self.assertEqual(len(result['error_rows']), 1)
        self.assertFalse(Medicine.objects.filter(short_name='ISOLATE-01').exists())
        self.assertTrue(Medicine.objects.filter(short_name='ISOLATE-02').exists())

    def test_import_preview_requires_confirmation_when_adding_same_file_twice(self):
        self._login_import_user()
        headers = ['name', 'short_name', 'pack_size', 'cost_price', 'selling_price', 'packs', 'units_per_pack']
        values = ['Ashwagandha Churna', 'ASH-RE', '100 gm', 50, 75, 3, 2]
        url = reverse('medicine:import_medicine')
        file_content = self._upload_file(headers, values).read()

        def same_file_upload():
            return SimpleUploadedFile(
                'medicines.xlsx',
                file_content,
                content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            )

        first_preview = self.client.post(url, {
            'action': 'upload',
            'stock_option': 'add',
            'excel_file': same_file_upload(),
        })
        self.assertEqual(first_preview.status_code, 200)
        self.assertFalse(Medicine.objects.filter(short_name='ASH-RE').exists())
        self.client.post(url, {'action': 'import'})
        variant = MedicineVariant.objects.get(medicine__short_name='ASH-RE')
        self.assertEqual(variant.stock, 6)

        second_preview = self.client.post(url, {
            'action': 'upload',
            'stock_option': 'add',
            'excel_file': same_file_upload(),
        })
        self.assertContains(second_preview, 'Importing again will add the stock twice.')
        blocked_import = self.client.post(url, {'action': 'import'})
        self.assertContains(blocked_import, 'I confirm adding this file again.')
        variant.refresh_from_db()
        self.assertEqual(variant.stock, 6)

        self.client.post(url, {'action': 'import', 'confirm_duplicate': 'on'})
        variant.refresh_from_db()
        self.assertEqual(variant.stock, 12)
