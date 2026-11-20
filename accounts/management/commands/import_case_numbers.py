import csv
import os
import re
from collections import defaultdict
from typing import Any, Dict, List

import openpyxl
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from accounts.models import FamilyMember, Patient


def normalize_name(name: Any) -> str:
    """Trim, collapse multiple spaces, and convert to lowercase for exact case-insensitive match."""
    if not name:
        return ""
    return re.sub(r"\s+", " ", str(name).strip()).lower()


def format_case_no(val: Any) -> str:
    """Store the number exactly as written, including multi-number values like '1691 / 1745'."""
    if val is None:
        return ""
    if isinstance(val, float) and val.is_integer():
        return str(int(val))
    return str(val).strip()


def format_matched_patient(matches: List[Dict[str, Any]]) -> str:
    """Format matched patients as type/id/name/phone."""
    if not matches:
        return ""
    formatted = []
    for m in matches:
        m_type = m["type"]
        m_id = str(m["id"])
        m_name = m["name"]
        m_phone = m["phone"] or ""
        formatted.append(f"{m_type}/{m_id}/{m_name}/{m_phone}")
    return "; ".join(formatted)


def has_effective_check_note(raw_note: str) -> bool:
    """
    Check if check_note has meaningful notes besides 'same name appears N times'.
    Splits on ';' and ignores parts that only say 'same name appears N times'.
    """
    if not raw_note:
        return False
    parts = raw_note.split(";")
    for part in parts:
        clean_part = part.strip()
        if not clean_part:
            continue
        if re.match(r"^same\s+name\s+appears\s+\d+\s+times?$", clean_part, re.IGNORECASE):
            continue
        return True
    return False


class Command(BaseCommand):
    help = "Fill Case No. for existing patients from old register Excel file."

    def add_arguments(self, parser):
        parser.add_argument("file", help="Path to the .xlsx file or file-like object")
        parser.add_argument(
            "--apply",
            action="store_true",
            default=False,
            help="Apply changes to the database. Without this flag, a dry run is performed.",
        )
        parser.add_argument(
            "--report",
            nargs="?",
            const="report.csv",
            default="report.csv",
            help="Path to CSV report output file (default: report.csv)",
        )

    def handle(self, *args, **options):
        file_input = options["file"]
        apply_changes = options["apply"]
        report_path = options["report"] or "report.csv"

        if isinstance(file_input, (str, os.PathLike)):
            if not os.path.exists(file_input):
                raise CommandError(f"File not found: {file_input}")
            wb = openpyxl.load_workbook(file_input, data_only=True)
        elif hasattr(file_input, "read") or hasattr(file_input, "seek"):
            if hasattr(file_input, "seek"):
                file_input.seek(0)
            wb = openpyxl.load_workbook(file_input, data_only=True)
        else:
            raise CommandError("Invalid file input: expected file path or file-like object.")

        sheet = wb.active
        raw_rows = list(sheet.iter_rows(values_only=True))
        if not raw_rows:
            self.stdout.write(self.style.WARNING("File is empty."))
            return

        header_row = raw_rows[0]
        col_map = {}
        for idx, cell in enumerate(header_row):
            if cell is None:
                continue
            raw_col = str(cell).strip().lower()
            clean_col = re.sub(r"[\s\-_]+", "_", raw_col)

            if clean_col in ("name", "patient_name", "full_name"):
                col_map["name"] = idx
            elif clean_col in ("old_register_no", "old_reg_no", "old_register_number"):
                col_map["case_no"] = idx
            elif clean_col in ("case_no", "caseno", "case_number") and "case_no" not in col_map:
                col_map["case_no"] = idx
            elif clean_col in ("check_note", "check_notes", "checknote", "note", "notes"):
                col_map["check_note"] = idx
            elif clean_col in ("page", "page_no", "page_number", "page_num"):
                col_map["page"] = idx

        if "name" not in col_map:
            raise CommandError("Missing required column 'name' in header.")
        if "case_no" not in col_map:
            raise CommandError("Missing required column 'old_register_no' (or 'case_no') in header.")

        # Build in-memory index of all Patients and FamilyMembers by normalized name
        patient_index = defaultdict(list)
        for p in Patient.objects.select_related("user").all():
            p_name = ""
            if p.user:
                p_name = f"{p.user.first_name} {p.user.last_name}".strip() or (p.user.get_full_name() or p.user.username)
            norm = normalize_name(p_name)
            if norm:
                patient_index[norm].append({
                    "type": "Patient",
                    "id": p.id,
                    "name": p_name,
                    "phone": p.phone or "",
                    "case_no": p.case_no or "",
                    "instance": p,
                })

        for m in FamilyMember.objects.all():
            m_name = m.name or ""
            norm = normalize_name(m_name)
            if norm:
                patient_index[norm].append({
                    "type": "FamilyMember",
                    "id": m.id,
                    "name": m_name,
                    "phone": m.phone or "",
                    "case_no": m.case_no or "",
                    "instance": m,
                })

        counts = {
            "will set": 0,
            "already set": 0,
            "conflict": 0,
            "multiple matches": 0,
            "not found": 0,
            "needs check": 0,
            "duplicate in register": 0,
        }

        # Count occurrences of each normalized name across all valid data rows in the Excel file
        excel_name_counts = defaultdict(int)
        for row in raw_rows[1:]:
            if not any(cell is not None and str(cell).strip() for cell in row):
                continue
            raw_name = row[col_map["name"]] if col_map["name"] < len(row) else ""
            norm = normalize_name(raw_name)
            if norm:
                excel_name_counts[norm] += 1

        report_rows = []
        to_update = []

        for row_idx, row in enumerate(raw_rows[1:], start=2):
            if not any(cell is not None and str(cell).strip() for cell in row):
                continue

            raw_name = row[col_map["name"]] if col_map["name"] < len(row) else ""
            raw_case_no = row[col_map["case_no"]] if col_map["case_no"] < len(row) else ""
            raw_check_note = row[col_map["check_note"]] if "check_note" in col_map and col_map["check_note"] < len(row) else ""
            raw_page = row[col_map["page"]] if "page" in col_map and col_map["page"] < len(row) else ""

            name_str = str(raw_name).strip() if raw_name is not None else ""
            case_no_str = format_case_no(raw_case_no)
            check_note_str = str(raw_check_note).strip() if raw_check_note is not None else ""
            if raw_page is None:
                page_str = ""
            elif isinstance(raw_page, float) and raw_page.is_integer():
                page_str = str(int(raw_page))
            else:
                page_str = str(raw_page).strip()

            norm_name = normalize_name(name_str)
            matches = patient_index.get(norm_name, []) if norm_name else []

            # Determine status
            if norm_name and excel_name_counts[norm_name] > 1:
                status = "duplicate in register"
            elif has_effective_check_note(check_note_str):
                status = "needs check"
            elif len(matches) == 0:
                status = "not found"
            elif len(matches) > 1:
                status = "multiple matches"
            else:
                match = matches[0]
                existing_case_no = (match["case_no"] or "").strip()
                if not existing_case_no:
                    status = "will set"
                    to_update.append((match["instance"], case_no_str))
                    # Update in-memory record so subsequent rows reflect this change
                    match["case_no"] = case_no_str
                elif existing_case_no == case_no_str:
                    status = "already set"
                else:
                    status = "conflict"

            counts[status] += 1

            report_rows.append({
                "row_number": row_idx,
                "page": page_str,
                "register_name": name_str,
                "case_no": case_no_str,
                "check_note": check_note_str,
                "status": status,
                "matched_patient": format_matched_patient(matches),
            })

        # Apply updates if requested
        if apply_changes and to_update:
            with transaction.atomic():
                for instance, target in to_update:
                    instance.case_no = target
                    instance.save(update_fields=["case_no"])

        # Write report.csv
        with open(report_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                "row_number",
                "page",
                "register_name",
                "case_no",
                "check_note",
                "status",
                "matched_patient",
            ])
            for r in report_rows:
                writer.writerow([
                    r["row_number"],
                    r["page"],
                    r["register_name"],
                    r["case_no"],
                    r["check_note"],
                    r["status"],
                    r["matched_patient"],
                ])

        # Print summary
        self.stdout.write(self.style.SUCCESS("Import Case Numbers Summary:"))
        for st in ("will set", "already set", "conflict", "multiple matches", "not found", "needs check", "duplicate in register"):
            self.stdout.write(f"  {st}: {counts[st]}")
        self.stdout.write(f"Total rows: {len(report_rows)}")

        if apply_changes:
            self.stdout.write(self.style.SUCCESS(f"Applied case numbers to {counts['will set']} records."))
        else:
            self.stdout.write(self.style.WARNING("Dry run complete. No records modified. (Use --apply to commit changes.)"))

        self.stdout.write(f"Report written to: {report_path}")
