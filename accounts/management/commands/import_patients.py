import os
from django.core.management.base import BaseCommand, CommandError
from accounts.services.patient_import import (
    parse_import_file,
    validate_patient_rows,
    create_patients_from_rows,
)


class Command(BaseCommand):
    help = "Import patients from a CSV or XLSX file."

    def add_arguments(self, parser):
        parser.add_argument("file_path", type=str, help="Path to the .csv or .xlsx file")
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Simulate the import process without writing to the database",
        )

    def handle(self, *args, **options):
        file_path = options["file_path"]
        dry_run = options["dry_run"]

        if not os.path.exists(file_path):
            raise CommandError(f"File not found: {file_path}")

        self.stdout.write(f"Reading file: {file_path} {'[DRY RUN]' if dry_run else ''}")

        try:
            with open(file_path, "rb") as f:
                raw_rows = parse_import_file(f)
        except Exception as e:
            raise CommandError(f"Failed to read file: {e}")

        if not raw_rows:
            self.stdout.write(self.style.WARNING("No data rows found in file."))
            return

        validated_rows = validate_patient_rows(raw_rows)
        results = create_patients_from_rows(validated_rows, dry_run=dry_run)

        self.stdout.write("\n" + "=" * 40)
        self.stdout.write(f"Total Rows:     {results['total']}")
        self.stdout.write(self.style.SUCCESS(f"Created:        {results['created_count']}"))
        self.stdout.write(self.style.WARNING(f"Duplicates:     {results['duplicate_count']}"))
        self.stdout.write(self.style.ERROR(f"Errors:         {results['error_count']}"))
        self.stdout.write("=" * 40 + "\n")

        if results["skipped_rows"]:
            self.stdout.write("Skipped Rows:")
            for s in results["skipped_rows"]:
                self.stdout.write(
                    f" - Row {s.get('row_num')}: {s.get('name')} ({s.get('phone')}) "
                    f"[{s.get('status')}] Reason: {s.get('reason')}"
                )
