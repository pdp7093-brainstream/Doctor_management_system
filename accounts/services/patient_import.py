import csv
import io
import re
from uuid import uuid4
from datetime import datetime
from typing import Dict, List, Tuple, Any

from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import transaction
from django.db.models import Q
from django.contrib.auth.models import User
from accounts.models import Patient

VALID_BLOOD_GROUPS = {"A+", "A-", "B+", "B-", "O+", "O-", "AB+", "AB-"}
VALID_GENDERS = {"male": "Male", "female": "Female", "other": "Other"}


def clean_phone(raw_phone: Any) -> Tuple[str, str]:
    """
    Cleans phone string.
    Strips spaces, dashes, parentheses and a leading +91 or 0.
    Returns (cleaned_phone, error_message).
    """
    if raw_phone is None:
        return "", ""

    s = str(raw_phone).strip()
    if not s:
        return "", ""

    # Remove floating point suffix if read from Excel as number (e.g. 9876543210.0)
    if s.endswith(".0"):
        s = s[:-2]

    # Strip spaces, dashes, dots, parentheses
    s = re.sub(r"[\s\-\.\(\)]+", "", s)

    # Strip leading +91 or 91 if length > 10, or leading 0
    if s.startswith("+91"):
        s = s[3:]
    elif s.startswith("91") and len(s) == 12:
        s = s[2:]
    elif s.startswith("0") and len(s) == 11:
        s = s[1:]

    if not s.isdigit() or len(s) != 10:
        return "", "Invalid phone number (must be 10 digits)"

    return s, ""


def clean_email(raw_email: Any) -> Tuple[str, str]:
    """
    Validates optional email.
    Returns (cleaned_email, error_message).
    """
    if raw_email is None:
        return "", ""
    s = str(raw_email).strip().lower()
    if not s:
        return "", ""
    try:
        validate_email(s)
        return s, ""
    except ValidationError:
        return "", "Invalid email address"


def clean_date(raw_dob: Any) -> Tuple[str, str]:
    """
    Accepts dd/mm/yyyy, dd-mm-yyyy, yyyy-mm-dd or datetime/date object.
    Returns (yyyy-mm-dd string, error_message).
    """
    if raw_dob is None:
        return "", ""
    if isinstance(raw_dob, datetime):
        return raw_dob.strftime("%Y-%m-%d"), ""
    if hasattr(raw_dob, "strftime"):
        return raw_dob.strftime("%Y-%m-%d"), ""

    s = str(raw_dob).strip()
    if not s:
        return "", ""

    # If datetime string with time component
    if " " in s:
        s = s.split(" ")[0].strip()

    for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(s, fmt)
            return dt.strftime("%Y-%m-%d"), ""
        except ValueError:
            pass

    return "", "Invalid date of birth format (expected dd/mm/yyyy, dd-mm-yyyy, or yyyy-mm-dd)"


def clean_gender(raw_gender: Any) -> str:
    """
    Male/Female/Other (case-insensitive), else blank.
    """
    if not raw_gender:
        return ""
    g = str(raw_gender).strip().lower()
    return VALID_GENDERS.get(g, "")


def clean_blood_group(raw_bg: Any) -> str:
    """
    Must be one of A+ A- B+ B- O+ O- AB+ AB- (case-insensitive), else blank.
    """
    if not raw_bg:
        return ""
    bg = str(raw_bg).strip().upper()
    return bg if bg in VALID_BLOOD_GROUPS else ""


def parse_import_file(uploaded_file) -> List[Dict[str, Any]]:
    """
    Reads CSV or XLSX uploaded file and returns a list of normalized row dictionaries.
    Keys: name, phone, email, gender, dob, blood_group, address.
    """
    filename = uploaded_file.name.lower()
    rows = []

    if filename.endswith(".csv"):
        # Detect encoding: try utf-8-sig, utf-8, latin-1
        content = uploaded_file.read()
        for encoding in ("utf-8-sig", "utf-8", "latin-1"):
            try:
                decoded = content.decode(encoding)
                break
            except UnicodeDecodeError:
                continue
        else:
            decoded = content.decode("utf-8", errors="replace")

        reader = csv.reader(io.StringIO(decoded))
        raw_rows = list(reader)
        if not raw_rows:
            return []

        header = [str(h).strip().lower() for h in raw_rows[0]]
        for row_idx, r in enumerate(raw_rows[1:], start=2):
            if not any(str(cell).strip() for cell in r):
                continue  # skip completely blank rows
            row_dict = {}
            for col_idx, col_name in enumerate(header):
                val = r[col_idx] if col_idx < len(r) else ""
                row_dict[col_name] = str(val).strip()
            rows.append({"_row_num": row_idx, **row_dict})

    elif filename.endswith((".xlsx", ".xlsm")):
        import openpyxl

        wb = openpyxl.load_workbook(uploaded_file, data_only=True)
        sheet = wb.active
        raw_rows = list(sheet.iter_rows(values_only=True))
        if not raw_rows:
            return []

        header = [str(h).strip().lower() if h is not None else "" for h in raw_rows[0]]
        for row_idx, r in enumerate(raw_rows[1:], start=2):
            if not any(cell is not None and str(cell).strip() for cell in r):
                continue
            row_dict = {}
            for col_idx, col_name in enumerate(header):
                if not col_name:
                    continue
                val = r[col_idx] if col_idx < len(r) else ""
                row_dict[col_name] = val if val is not None else ""
            rows.append({"_row_num": row_idx, **row_dict})

    else:
        raise ValueError("Unsupported file format. Please upload a .csv or .xlsx file.")

    return rows


def validate_patient_rows(raw_rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Validates a list of parsed rows and determines each row's status:
    'New', 'Duplicate', or 'Error' (with reason).

    Tracks seen phones and emails within the file and against existing database records.
    """
    existing_phones = set(
        Patient.objects.exclude(phone__isnull=True)
        .exclude(phone__exact="")
        .values_list("phone", flat=True)
    )
    existing_name_only_patients = {
        f"{first_name} {last_name}".strip()
        for first_name, last_name in Patient.objects.filter(
            Q(phone__isnull=True) | Q(phone="")
        ).values_list("user__first_name", "user__last_name")
    }

    existing_emails = set(
        User.objects.exclude(email__isnull=True)
        .exclude(email__exact="")
        .values_list("email", flat=True)
    )
    existing_usernames = set(User.objects.values_list("username", flat=True))

    seen_phones_in_file = set()
    seen_name_only_in_file = set()
    seen_emails_in_file = set()

    validated_rows = []

    for idx, r in enumerate(raw_rows, start=1):
        row_num = r.get("_row_num", idx + 1)
        name = str(r.get("name", "")).strip()
        raw_phone = r.get("phone", "")
        raw_email = r.get("email", "")
        raw_gender = r.get("gender", "")
        raw_dob = r.get("dob", "")
        raw_bg = r.get("blood_group", "")
        address = str(r.get("address", "")).strip()

        errors = []

        # Required: name
        if not name:
            errors.append("Missing name")

        # Optional: phone
        phone, phone_err = clean_phone(raw_phone)
        if phone_err:
            errors.append(phone_err)

        # Optional: email
        email, email_err = clean_email(raw_email)
        if email_err:
            errors.append(email_err)

        # Optional: dob
        dob_str, dob_err = clean_date(raw_dob)
        if dob_err:
            errors.append(dob_err)

        gender = clean_gender(raw_gender)
        bld_grop = clean_blood_group(raw_bg)

        if errors:
            status = "Error"
            reason = "; ".join(errors)
        else:
            # Check duplicate in file or DB
            is_dup = False
            dup_reasons = []

            # Check phone
            if phone:
                if phone in seen_phones_in_file:
                    is_dup = True
                    dup_reasons.append(f"Phone {phone} appears multiple times in file")
                elif phone in existing_phones:
                    is_dup = True
                    dup_reasons.append(f"Patient with phone {phone} already exists")
            elif name in seen_name_only_in_file or name in existing_name_only_patients:
                is_dup = True
                dup_reasons.append("Duplicate (same name, no phone)")

            # Check email if provided
            if email:
                if email in seen_emails_in_file:
                    is_dup = True
                    dup_reasons.append(f"Email {email} appears multiple times in file")
                elif email in existing_emails or email in existing_usernames:
                    is_dup = True
                    dup_reasons.append(f"User with email/username {email} already exists")

            if is_dup:
                status = "Duplicate"
                reason = "; ".join(dup_reasons)
            else:
                status = "New"
                reason = "Ready (no phone)" if not phone else ""
                if phone:
                    seen_phones_in_file.add(phone)
                else:
                    seen_name_only_in_file.add(name)
                if email:
                    seen_emails_in_file.add(email)

        validated_rows.append({
            "row_num": row_num,
            "name": name,
            "phone": phone,
            "email": email,
            "gender": gender,
            "dob": dob_str,
            "blood_group": bld_grop,
            "address": address,
            "status": status,
            "reason": reason,
        })

    return validated_rows


def create_patients_from_rows(rows: List[Dict[str, Any]], dry_run: bool = False) -> Dict[str, Any]:
    """
    Creates Patient records for rows marked as 'New'.
    Re-checks duplicates right before creation.
    Each row runs inside its own transaction.atomic().

    Returns summary dictionary:
      total: int
      created_count: int
      duplicate_count: int
      error_count: int
      created_patients: List[Dict]
      skipped_rows: List[Dict] (includes original duplicates, errors, or runtime failures)
    """
    created_count = 0
    duplicate_count = 0
    error_count = 0
    skipped_rows = []
    created_patients = []

    for r in rows:
        status = r.get("status")
        if status == "Error":
            error_count += 1
            skipped_rows.append(r)
            continue
        elif status == "Duplicate":
            duplicate_count += 1
            skipped_rows.append(r)
            continue

        # If it was 'New', create it (or simulate if dry_run)
        phone = r.get("phone") or None
        email = r.get("email", "")
        name = r.get("name", "")
        gender = r.get("gender", "") or None
        dob = r.get("dob", "") or None
        bld_grop = r.get("blood_group", "") or None
        address = r.get("address", "") or ""

        # Runtime duplicate re-check
        name_parts = name.split(" ", 1)
        first_name = name_parts[0]
        last_name = name_parts[1] if len(name_parts) > 1 else ""
        if phone and Patient.objects.filter(phone=phone).exists():
            duplicate_count += 1
            r_skipped = dict(r)
            r_skipped["status"] = "Duplicate"
            r_skipped["reason"] = f"Patient with phone {phone} already exists"
            skipped_rows.append(r_skipped)
            continue
        if not phone and Patient.objects.filter(
            Q(phone__isnull=True) | Q(phone=""),
            user__first_name=first_name,
            user__last_name=last_name,
        ).exists():
            duplicate_count += 1
            r_skipped = dict(r)
            r_skipped["status"] = "Duplicate"
            r_skipped["reason"] = "Duplicate (same name, no phone)"
            skipped_rows.append(r_skipped)
            continue

        username = email if email else f"pt-{phone}" if phone else f"pt-{uuid4().hex}"
        if email and (User.objects.filter(email__iexact=email).exists() or User.objects.filter(username__iexact=email).exists()):
            duplicate_count += 1
            r_skipped = dict(r)
            r_skipped["status"] = "Duplicate"
            r_skipped["reason"] = f"User with email/username {email} already exists"
            skipped_rows.append(r_skipped)
            continue

        if not email and User.objects.filter(username__iexact=username).exists():
            duplicate_count += 1
            r_skipped = dict(r)
            r_skipped["status"] = "Duplicate"
            r_skipped["reason"] = f"User with username {username} already exists"
            skipped_rows.append(r_skipped)
            continue

        if dry_run:
            created_count += 1
            created_patients.append(r)
            continue

        # Execute creation inside transaction.atomic()
        try:
            with transaction.atomic():
                user = User.objects.create_user(
                    username=username,
                    email=email,
                    first_name=first_name,
                    last_name=last_name,
                )
                user.set_unusable_password()
                user.save()

                patient = user.patient
                patient.phone = phone
                patient.address = address
                patient.dob = dob
                patient.gender = gender
                patient.bld_grop = bld_grop
                patient.save()

            created_count += 1
            created_patients.append(r)

        except Exception as exc:
            error_count += 1
            r_err = dict(r)
            r_err["status"] = "Error"
            r_err["reason"] = f"Database error: {str(exc)}"
            skipped_rows.append(r_err)

    return {
        "total": len(rows),
        "created_count": created_count,
        "duplicate_count": duplicate_count,
        "error_count": error_count,
        "created_patients": created_patients,
        "skipped_rows": skipped_rows,
    }


def generate_sample_csv() -> str:
    """
    Generates a sample CSV string with headers and 2 example rows.
    """
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["name", "phone", "email", "gender", "dob", "blood_group", "address"])
    writer.writerow(["Aarav Sharma", "9876543210", "aarav@example.com", "Male", "15/08/1990", "B+", "123 Green Park, New Delhi"])
    writer.writerow(["Pooja Patel", "9123456780", "", "Female", "1995-12-04", "O+", "45 Ashram Road, Ahmedabad"])
    return output.getvalue()
