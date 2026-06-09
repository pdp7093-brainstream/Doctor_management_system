import logging
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from .models import Patient

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
            instance.patient.save()
    except Exception as exc:
        logger.warning(
            "Could not save Patient profile for user '%s': %s",
            instance.username,
            exc,
        )
