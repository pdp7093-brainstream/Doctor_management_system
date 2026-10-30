import logging
import glob
import os

from django.conf import settings
from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from .models import FamilyMember, Patient
from appointment.upload_paths import member_folder, patient_folder

logger = logging.getLogger(__name__)


@receiver(post_save, sender=User)
def create_patient_profile(sender, instance, created, **kwargs):
    """
    Auto-create a Patient profile whenever a new non-staff User is saved.
    Uses get_or_create to be idempotent (safe if called multiple times).
    """
    if created and not instance.is_staff and not instance.is_superuser:
        patient, was_created = Patient.objects.get_or_create(user=instance)
        if was_created:
            logger.info(
                "Patient profile created for user '%s' (id=%s)",
                instance.username,
                instance.pk,
            )


@receiver(post_save, sender=User)
def save_patient_profile(sender, instance, **kwargs):
    """
    Propagate User saves to the linked Patient profile when it exists.
    """
    try:
        if hasattr(instance, 'patient'):
            patient = instance.patient
            patient.refresh_from_db()
            patient.save()
    except Exception as exc:
        logger.warning(
            "Could not save Patient profile for user '%s': %s",
            instance.username,
            exc,
        )


def _update_file_prefixes(old_prefix, new_prefix):
    from appointment.models import LabDocument, PatientOldDocument, PatientUploadedDocument

    file_fields = (
        (Patient, 'profile_picture'),
        (PatientUploadedDocument, 'file'),
        (PatientOldDocument, 'file'),
        (LabDocument, 'file'),
    )
    old_prefix_with_separator = f'{old_prefix}/'
    for model, field_name in file_fields:
        matching_files = model.objects.filter(
            **{f'{field_name}__startswith': old_prefix_with_separator}
        ).values_list('pk', field_name)
        for object_id, file_name in matching_files.iterator():
            model.objects.filter(pk=object_id).update(
                **{field_name: f'{new_prefix}{file_name[len(old_prefix):]}'}
            )


def _rename_media_folder(folder_pattern, new_relative_folder):
    old_path = next(
        (path for path in glob.glob(folder_pattern) if os.path.isdir(path)),
        None,
    )
    if old_path is None:
        return

    old_relative_folder = os.path.relpath(old_path, settings.MEDIA_ROOT).replace(os.sep, '/')
    if old_relative_folder == new_relative_folder:
        return

    new_path = os.path.join(settings.MEDIA_ROOT, new_relative_folder)
    with transaction.atomic():
        _update_file_prefixes(old_relative_folder, new_relative_folder)
        try:
            os.rename(old_path, new_path)
        except OSError:
            logger.exception(
                "Could not rename media folder '%s' to '%s'",
                old_path,
                new_path,
            )
            raise


@receiver(post_save, sender=User)
def sync_patient_media_folder(sender, instance, **kwargs):
    try:
        patient = Patient.objects.select_related('user').get(user_id=instance.pk)
    except Patient.DoesNotExist:
        return

    _rename_media_folder(
        os.path.join(settings.MEDIA_ROOT, 'patients', f'{patient.pk}_*'),
        patient_folder(patient),
    )


@receiver(post_save, sender=FamilyMember)
def sync_family_member_media_folder(sender, instance, **kwargs):
    patient = Patient.objects.select_related('user').get(pk=instance.patient_id)
    patient_path = patient_folder(patient)
    family_path = os.path.join(settings.MEDIA_ROOT, patient_path, 'family')
    _rename_media_folder(
        os.path.join(family_path, f'{instance.pk}_*'),
        f'{patient_path}/{member_folder(instance)}',
    )
