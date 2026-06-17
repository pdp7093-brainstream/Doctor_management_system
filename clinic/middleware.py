from django.shortcuts import redirect
from django.urls import reverse


SETUP_URL_PREFIX = '/clinic/setup/'
EXEMPT_PREFIXES = ('/static/', '/media/', '/admin/')


class SetupRequiredMiddleware:
    """
    Checks on each request whether a clinic owner exists.
    If not, redirects to the setup wizard.
    Once setup is complete this middleware becomes transparent.
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self._setup_done = None  # Cache to avoid DB hits on every request

    def __call__(self, request):
        path = request.path

        # Bypass static/media/admin files
        if any(path.startswith(p) for p in EXEMPT_PREFIXES):
            return self.get_response(request)

        # Bypass setup pages (prefix-based check)
        if path.startswith(SETUP_URL_PREFIX):
            return self.get_response(request)

        # Cache check — skip if setup already completed
        if self._setup_done:
            return self.get_response(request)

        # Lazy import to avoid app-registry issues at startup
        try:
            from doctor.models import InnerMember
            owner_exists = InnerMember.objects.filter(is_owner=True).exists()
        except Exception:
            # DB table not created yet (before fresh migrate) — skip
            return self.get_response(request)

        if owner_exists:
            self._setup_done = True  # Cache kar lo
            return self.get_response(request)

        # No owner found → redirect to setup wizard
        setup_url = reverse('clinic:setup_clinic')
        return redirect(setup_url)
