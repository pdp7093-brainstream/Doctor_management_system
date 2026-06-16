import os

from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils.text import get_valid_filename


ALLOWED_DOCUMENT_EXTENSIONS = {
    ".pdf", ".jpg", ".jpeg", ".png", ".gif", ".webp", ".doc", ".docx",
}

MAX_DOCUMENT_UPLOAD_SIZE = getattr(
    settings,
    "DOCUMENT_UPLOAD_MAX_SIZE",
    10 * 1024 * 1024,
)

BLOCKED_MAGIC_HEADERS = (
    b"MZ",  # Windows PE/EXE
    b"\x7fELF",  # Linux executable
)


def clean_original_filename(filename):
    basename = os.path.basename(filename or "document")
    cleaned = get_valid_filename(basename)
    return cleaned[:255] or "document"


def _read_header(uploaded_file, length=16):
    position = None
    if hasattr(uploaded_file, "tell"):
        try:
            position = uploaded_file.tell()
        except (OSError, ValueError):
            position = None

    header = uploaded_file.read(length)

    if hasattr(uploaded_file, "seek"):
        try:
            uploaded_file.seek(position or 0)
        except (OSError, ValueError):
            pass

    return header or b""


def _has_allowed_signature(extension, header):
    checks = {
        ".pdf": lambda data: data.startswith(b"%PDF-"),
        ".jpg": lambda data: data.startswith(b"\xff\xd8\xff"),
        ".jpeg": lambda data: data.startswith(b"\xff\xd8\xff"),
        ".png": lambda data: data.startswith(b"\x89PNG\r\n\x1a\n"),
        ".gif": lambda data: data.startswith((b"GIF87a", b"GIF89a")),
        ".webp": lambda data: data.startswith(b"RIFF") and data[8:12] == b"WEBP",
        ".doc": lambda data: data.startswith(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"),
        ".docx": lambda data: data.startswith(b"PK\x03\x04"),
    }
    return checks[extension](header)


def validate_uploaded_document(uploaded_file):
    if not uploaded_file:
        raise ValidationError("Please choose a document to upload.")

    original_name = clean_original_filename(getattr(uploaded_file, "name", ""))
    extension = os.path.splitext(original_name)[1].lower()

    if extension not in ALLOWED_DOCUMENT_EXTENSIONS:
        allowed = ", ".join(sorted(ALLOWED_DOCUMENT_EXTENSIONS))
        raise ValidationError(f"Unsupported file type. Allowed types: {allowed}.")

    size = getattr(uploaded_file, "size", 0) or 0
    if size <= 0:
        raise ValidationError("Uploaded file is empty.")
    if size > MAX_DOCUMENT_UPLOAD_SIZE:
        max_mb = MAX_DOCUMENT_UPLOAD_SIZE // (1024 * 1024)
        raise ValidationError(f"Uploaded file is too large. Maximum size is {max_mb} MB.")

    header = _read_header(uploaded_file)
    if header.startswith(BLOCKED_MAGIC_HEADERS):
        raise ValidationError("Executable files are not allowed.")

    if not _has_allowed_signature(extension, header):
        raise ValidationError("File content does not match the selected file type.")

    return original_name
