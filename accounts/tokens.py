from datetime import timezone as datetime_timezone

from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.utils.crypto import constant_time_compare
from django.utils.http import base36_to_int
from django.utils import timezone


class PatientInviteTokenGenerator(PasswordResetTokenGenerator):
    key_salt = 'accounts.patient_invite'
    timeout_seconds = 48 * 60 * 60

    def _now(self):
        return timezone.now()

    def _num_seconds(self, dt):
        if timezone.is_aware(dt):
            dt = timezone.make_naive(dt, datetime_timezone.utc)
        return super()._num_seconds(dt)

    def check_token(self, user, token):
        if not (user and token):
            return False
        try:
            timestamp_b36, _ = token.split('-')
        except ValueError:
            return False
        try:
            timestamp = base36_to_int(timestamp_b36)
        except ValueError:
            return False

        for secret in [self.secret, *self.secret_fallbacks]:
            if constant_time_compare(self._make_token_with_timestamp(user, timestamp, secret), token):
                break
        else:
            return False
        age = self._num_seconds(self._now()) - timestamp
        return 0 <= age <= self.timeout_seconds


patient_invite_token_generator = PatientInviteTokenGenerator()
