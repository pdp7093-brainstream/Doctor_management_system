import os
import posixpath
import uuid

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction

from accounts.models import Patient
from appointment.models import (
    LabDocument,
    PatientOldDocument,
    PatientUploadedDocument,
)
from doctor.models import InnerMember


FILE_FIELDS = (
    (Patient, 'profile_picture'),
    (PatientUploadedDocument, 'file'),
    (PatientOldDocument, 'file'),
    (LabDocument, 'file'),
    (InnerMember, 'profile_picture'),
)
DEFAULT_PATIENT_AVATAR = 'profile_pictures/default-avatar.png'
OLD_MEDIA_FOLDERS = (
    'lab_documents',
    'patient_documents',
    'old_patient_data',
    'profile_pictures',
)


class Command(BaseCommand):
    help = 'Move existing media files to their current upload_to locations.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Print planned moves without changing files or database rows.',
        )

    def handle(self, *args, **options):
        self.dry_run = options['dry_run']
        self.counts = {'moved': 0, 'skipped': 0, 'missing': 0}

        for model, field_name in FILE_FIELDS:
            for instance in model.objects.all().iterator():
                self._migrate_file(instance, field_name)

        self.stdout.write(
            'Counts: moved={moved} skipped={skipped} missing={missing}'.format(
                **self.counts
            )
        )
        self._report_unreferenced_files()

    def _migrate_file(self, instance, field_name):
        file_field = instance._meta.get_field(field_name)
        current_file = getattr(instance, field_name)
        old_name = current_file.name

        if not old_name:
            self.counts['skipped'] += 1
            self.stdout.write('<empty> -> <empty> (SKIPPED)')
            return

        basename = posixpath.basename(old_name.replace('\\', '/'))
        new_name = file_field.upload_to(instance, basename)

        if (
            instance.__class__ is Patient
            and field_name == 'profile_picture'
            and old_name == DEFAULT_PATIENT_AVATAR
        ):
            self.counts['skipped'] += 1
            self.stdout.write(f'{old_name} -> {new_name} (SKIPPED default avatar)')
            return

        new_folder = posixpath.dirname(new_name).rstrip('/')
        old_path = self._disk_path(old_name)
        if old_path is None:
            self.counts['skipped'] += 1
            self.stdout.write(f'{old_name} -> {new_name} (SKIPPED invalid path)')
            return

        if not os.path.isfile(old_path):
            self.counts['missing'] += 1
            self.stdout.write(f'MISSING {old_name} -> {new_name}')
            return

        if old_name.replace('\\', '/').startswith(f'{new_folder}/'):
            self.counts['skipped'] += 1
            self.stdout.write(f'{old_name} -> {new_name} (SKIPPED already current)')
            return

        new_name = self._unique_target(new_name)
        self.stdout.write(f'{old_name} -> {new_name}')
        if self.dry_run:
            self.counts['skipped'] += 1
            return

        new_path = self._disk_path(new_name)
        if new_path is None:
            self.counts['skipped'] += 1
            self.stderr.write(f'SKIPPED invalid target: {new_name}')
            return

        try:
            with transaction.atomic():
                os.makedirs(os.path.dirname(new_path), exist_ok=True)
                os.rename(old_path, new_path)
                setattr(instance, field_name, new_name)
                try:
                    instance.save(update_fields=[field_name])
                except Exception:
                    os.rename(new_path, old_path)
                    raise
        except Exception as exc:
            self.counts['skipped'] += 1
            self.stderr.write(f'FAILED {old_name}: {exc}')
            return

        self.counts['moved'] += 1

    def _disk_path(self, relative_path):
        media_root = os.path.realpath(settings.MEDIA_ROOT)
        disk_path = os.path.realpath(
            os.path.join(media_root, relative_path.replace('\\', '/'))
        )
        try:
            if os.path.commonpath((media_root, disk_path)) != media_root:
                return None
        except ValueError:
            return None
        return disk_path

    def _unique_target(self, relative_path):
        directory, filename = posixpath.split(relative_path)
        stem, extension = posixpath.splitext(filename)
        candidate = relative_path
        while True:
            disk_path = self._disk_path(candidate)
            if disk_path is None or not os.path.lexists(disk_path):
                return candidate
            candidate = posixpath.join(
                directory,
                f'{stem}_{uuid.uuid4().hex[:6]}{extension}',
            )

    def _report_unreferenced_files(self):
        referenced = set()
        for model, field_name in FILE_FIELDS:
            for name in model.objects.values_list(field_name, flat=True).iterator():
                if name:
                    referenced.add(name.replace('\\', '/'))

        root_files = []
        try:
            for entry in os.scandir(settings.MEDIA_ROOT):
                if entry.is_file():
                    root_files.append(entry.name)
        except FileNotFoundError:
            pass

        self.stdout.write('Unreferenced files in MEDIA_ROOT root:')
        self._print_unreferenced(root_files, referenced)

        for folder in OLD_MEDIA_FOLDERS:
            old_folder_path = os.path.join(settings.MEDIA_ROOT, folder)
            candidates = []
            for directory, _, filenames in os.walk(old_folder_path):
                for filename in filenames:
                    disk_path = os.path.join(directory, filename)
                    relative_path = os.path.relpath(
                        disk_path, settings.MEDIA_ROOT
                    ).replace(os.sep, '/')
                    candidates.append(relative_path)
            self.stdout.write(f'Unreferenced files in {folder}/:')
            self._print_unreferenced(candidates, referenced)

    def _print_unreferenced(self, candidates, referenced):
        unreferenced = sorted(set(candidates) - referenced)
        if not unreferenced:
            self.stdout.write('  (none)')
            return
        for relative_path in unreferenced:
            self.stdout.write(f'  {relative_path}')