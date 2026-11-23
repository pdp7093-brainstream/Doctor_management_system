from collections import defaultdict

from django.core.management.base import BaseCommand

from accounts.models import FamilyMember, Patient


class Command(BaseCommand):
    help = 'List case numbers assigned to more than one patient or family member.'

    def handle(self, *args, **options):
        records_by_case_no = defaultdict(list)

        for patient in Patient.objects.select_related('user').exclude(case_no='').iterator():
            case_no = (patient.case_no or '').strip()
            if case_no:
                records_by_case_no[case_no.casefold()].append({
                    'case_no': case_no,
                    'type': 'Patient',
                    'id': patient.pk,
                    'name': patient.user.get_full_name() or patient.user.email or patient.user.username,
                    'phone': patient.phone or '',
                })

        for member in FamilyMember.objects.exclude(case_no='').iterator():
            case_no = (member.case_no or '').strip()
            if case_no:
                records_by_case_no[case_no.casefold()].append({
                    'case_no': case_no,
                    'type': 'FamilyMember',
                    'id': member.pk,
                    'name': member.name,
                    'phone': member.phone or '',
                })

        self.stdout.write('case_no\ttype\tid\tname\tphone')
        duplicate_count = 0
        for normalized_case_no in sorted(records_by_case_no):
            records = records_by_case_no[normalized_case_no]
            if len(records) < 2:
                continue
            duplicate_count += 1
            for record in records:
                self.stdout.write(
                    f"{record['case_no']}\t{record['type']}\t{record['id']}\t"
                    f"{record['name']}\t{record['phone']}"
                )

        if not duplicate_count:
            self.stdout.write('No duplicate case numbers found.')
