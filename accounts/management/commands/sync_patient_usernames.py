from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db.models import Q


class Command(BaseCommand):
    help = 'Set linked patient usernames to their email addresses.'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Report changes without saving them.')

    def handle(self, *args, **options):
        user_model = get_user_model()
        dry_run = options['dry_run']
        updated = 0
        conflicts = 0

        users = user_model.objects.filter(patient__isnull=False).exclude(email__isnull=True).exclude(email='')
        for user in users.iterator():
            email = user.email.lower()
            if user.username.casefold() == email.casefold():
                continue

            email_in_use = user_model.objects.filter(
                Q(email__iexact=email) | Q(username__iexact=email)
            ).exclude(pk=user.pk).exists()
            if email_in_use:
                conflicts += 1
                self.stdout.write(self.style.WARNING(
                    f'Conflict for patient user {user.pk}: {email} is already in use.'
                ))
                continue

            if dry_run:
                self.stdout.write(f'Would update patient user {user.pk}: username -> {email}')
            else:
                user.username = email
                user.save(update_fields=['username'])
                updated += 1

        if dry_run:
            self.stdout.write(f'Dry run complete: {conflicts} conflict(s).')
        else:
            self.stdout.write(self.style.SUCCESS(
                f'Updated {updated} patient username(s); {conflicts} conflict(s).'
            ))