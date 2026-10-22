from django.test import TestCase
from django.contrib.auth.models import User
from accounts.models import Patient
from accounts.services.patient_import import (
    clean_phone,
    clean_date,
    validate_patient_rows,
    create_patients_from_rows,
)


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
        self.assertTrue("Missing phone" in err)

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
