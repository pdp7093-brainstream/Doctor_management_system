import logging
from datetime import date

from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import EmailMultiAlternatives
from django.db import transaction
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from clinic.models import ClinicSettings


logger = logging.getLogger(__name__)


def send_welcome_email(request, user, phone='', added_by_clinic=False):
    if not user.email:
        return

    try:
        try:
            clinic = ClinicSettings.get()
        except Exception:
            logger.exception('Unable to load clinic settings for welcome email')
            clinic = None

        clinic_name = getattr(clinic, 'clinic_name', None) or 'Clinic'
        logo_url = ''
        if clinic and clinic.logo:
            try:
                logo_url = request.build_absolute_uri(clinic.logo.url)
            except (AttributeError, ValueError):
                pass

        start_time = getattr(clinic, 'start_time', None)
        end_time = getattr(clinic, 'end_time', None)
        hours = ''
        if start_time and end_time:
            hours = f'{start_time.strftime("%I:%M %p")} – {end_time.strftime("%I:%M %p")}'

        working_days = ''
        if clinic and clinic.working_days:
            day_names = dict(ClinicSettings.WORKING_DAYS_CHOICES)
            working_days = ', '.join(
                day_names.get(day.strip().lower(), day.strip().title())
                for day in clinic.working_days.split(',')
                if day.strip()
            )

        set_password_url = ''
        if added_by_clinic:
            uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
            token = default_token_generator.make_token(user)
            path = reverse(
                'password_reset_confirm',
                kwargs={'uidb64': uidb64, 'token': token},
            )
            set_password_url = request.build_absolute_uri(path)

        context = {
            'name': user.first_name or user.username,
            'email': user.email,
            'phone': phone or '',
            'clinic_name': clinic_name,
            'tagline': getattr(clinic, 'tagline', None) or '',
            'logo_url': logo_url,
            'login_url': request.build_absolute_uri(reverse('login')),
            'booking_url': request.build_absolute_uri(reverse('appointment:appointment')),
            'set_password_url': set_password_url,
            'added_by_clinic': added_by_clinic,
            'address': getattr(clinic, 'address', None) or '',
            'clinic_phone': getattr(clinic, 'phone', None) or '',
            'hours': hours,
            'working_days': working_days,
            'year': date.today().year,
        }

        subject = ' '.join(render_to_string('emails/welcome_subject.txt', context).splitlines()).strip()
        text = render_to_string('emails/welcome.txt', context)
        html = render_to_string('emails/welcome.html', context)
        message = EmailMultiAlternatives(
            subject=subject,
            body=text,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[user.email],
        )
        message.attach_alternative(html, 'text/html')

        def send():
            try:
                message.send()
            except Exception:
                logger.exception('Unable to send welcome email to %s', user.email)

        transaction.on_commit(send)
    except Exception:
        logger.exception('Unable to prepare welcome email for %s', user.email)