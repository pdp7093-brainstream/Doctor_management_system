import logging
from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.mail import EmailMultiAlternatives
from django.core.validators import validate_email
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from accounts.tokens import patient_invite_token_generator

logger = logging.getLogger(__name__)
security_logger = logging.getLogger('accounts.security')


def send_patient_invite_email(patient, request, acting_user):
    """Send a patient password setup invite and persist the invite timestamp."""
    email = (patient.user.email or '').strip()
    if not email:
        return 'no_email', email
    try:
        validate_email(email)
    except ValidationError:
        return 'invalid_email', email
    if patient.login_status == 'active':
        return 'active', email

    now = timezone.now()
    if patient.invite_sent_at and now - patient.invite_sent_at < timedelta(minutes=2):
        return 'recent', email

    uidb64 = urlsafe_base64_encode(force_bytes(patient.user_id))
    token = patient_invite_token_generator.make_token(patient.user)
    invite_url = request.build_absolute_uri(reverse(
        'activate_patient', kwargs={'uidb64': uidb64, 'token': token}
    ))
    context = {'patient': patient, 'invite_url': invite_url}
    try:
        message = EmailMultiAlternatives(
            subject='Set your Hitshree patient account password',
            body=render_to_string('emails/patient_invite.txt', context),
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[email],
        )
        message.attach_alternative(render_to_string('emails/patient_invite.html', context), 'text/html')
        message.send(fail_silently=False)
    except Exception:
        logger.exception('Unable to send patient invite for patient_id=%s', patient.pk)
        return 'error', email

    patient.invite_sent_at = now
    patient.save(update_fields=['invite_sent_at'])
    security_logger.info(
        'patient_invite_sent patient_id=%s user_id=%s actor_user_id=%s',
        patient.pk, patient.user_id, acting_user.pk,
    )
    return 'sent', email
