from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase

from .file_validation import clean_original_filename, validate_uploaded_document


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
