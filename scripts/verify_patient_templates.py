import os
import sys
from html.parser import HTMLParser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "doctor_mgmt.settings")

import django
from django.conf import settings
from django.test import Client, override_settings
from django.test.utils import setup_databases, setup_test_environment, teardown_databases, teardown_test_environment
from django.urls import reverse
from django.utils import timezone


class IncludeParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.html_count = 0
        self.head_count = 0
        self.css = []
        self.js = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "html":
            self.html_count += 1
        elif tag == "head":
            self.head_count += 1
        elif tag == "link" and attrs.get("rel") and "stylesheet" in attrs.get("rel"):
            self.css.append(attrs.get("href", ""))
        elif tag == "script" and attrs.get("src"):
            self.js.append(attrs.get("src", ""))


def duplicates(items):
    seen = set()
    dupes = []
    for item in items:
        if item in seen and item not in dupes:
            dupes.append(item)
        seen.add(item)
    return dupes


def main():
    django.setup()
    from django.contrib.auth.models import User
    setup_test_environment()
    old_config = setup_databases(verbosity=0, interactive=False)
    try:
        from accounts.models import Patient
        from appointment.models import Appointment
        from clinic.models import ClinicSettings
        from doctor.models import InnerMember
        from doctor import hashid

        ClinicSettings.get()
        owner_user = User.objects.create_user(username="owner-template-test@example.com", password="owner-pass")
        InnerMember.objects.create(user=owner_user, role="doctor", is_owner=True)

        user = User.objects.create_user(
            username="patient-template-test@example.com",
            email="patient-template-test@example.com",
            password="template-test-pass",
            first_name="Patient",
        )
        patient, _ = Patient.objects.get_or_create(user=user, defaults={"phone": "9000000001"})
        if not patient.phone:
            patient.phone = "9000000001"
            patient.save(update_fields=["phone"])
        appointment = Appointment.objects.create(
            patient=patient,
            booked_by=user,
            appointment_date=timezone.localdate(),
            time_slot="10:00",
            status="pending",
        )

        public_urls = [
            reverse("index"),
            reverse("about"),
            reverse("departments"),
            reverse("services"),
            reverse("feedback"),
            reverse("terms"),
            reverse("login"),
            reverse("signup"),
        ]
        private_urls = [
            reverse("appointment:appointment"),
            reverse("dashboard"),
            reverse("profile"),
            reverse("appointment:appointment_detail", args=[hashid.encode_id(appointment.id)]),
            reverse("resetpass"),
        ]

        middleware = [mw for mw in settings.MIDDLEWARE if not mw.startswith("whitenoise.")]
        with override_settings(ALLOWED_HOSTS=["testserver"], MIDDLEWARE=middleware):
            anonymous = Client()
            authenticated = Client()
            authenticated.force_login(user)

            failures = []
            for url in public_urls:
                response = anonymous.get(url)
                failures.extend(check_response(url, response))

            for url in private_urls:
                response = authenticated.get(url)
                failures.extend(check_response(url, response))

            if failures:
                raise SystemExit("\n".join(failures))

            print("OK: all converted URLs returned 200, one html/head each, with no duplicate CSS/JS includes.")
    finally:
        teardown_databases(old_config, verbosity=0)
        teardown_test_environment()


def check_response(url, response):
    failures = []
    if response.status_code != 200:
        failures.append(f"{url}: expected 200, got {response.status_code}")
        return failures

    html = response.content.decode(response.charset or "utf-8", errors="replace")
    parser = IncludeParser()
    parser.feed(html)

    if parser.html_count != 1:
        failures.append(f"{url}: expected one <html>, found {parser.html_count}")
    if parser.head_count != 1:
        failures.append(f"{url}: expected one <head>, found {parser.head_count}")

    css_dupes = duplicates(parser.css)
    js_dupes = duplicates(parser.js)
    if css_dupes:
        failures.append(f"{url}: duplicate CSS includes: {css_dupes}")
    if js_dupes:
        failures.append(f"{url}: duplicate JS includes: {js_dupes}")

    return failures


if __name__ == "__main__":
    main()
