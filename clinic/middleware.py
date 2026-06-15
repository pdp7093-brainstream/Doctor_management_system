from django.shortcuts import redirect
from django.urls import reverse


SETUP_URL_PREFIX = '/clinic/setup/'
EXEMPT_PREFIXES = ('/static/', '/media/', '/admin/')


class SetupRequiredMiddleware:
    """
    Har request pe check karta hai ki clinic owner exist karta hai ya nahi.
    Agar nahi, toh setup wizard pe redirect karta hai.
    Jab ek baar setup complete ho jaye toh yeh middleware transparent ho jata hai.
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self._setup_done = None  # Cache taaki har request pe DB hit na ho

    def __call__(self, request):
        path = request.path

        # Static/media/admin files ko bypass karo
        if any(path.startswith(p) for p in EXEMPT_PREFIXES):
            return self.get_response(request)

        # Setup pages khud bypass hongi (prefix-based check)
        if path.startswith(SETUP_URL_PREFIX):
            return self.get_response(request)

        # Cache check — agar already setup hua hai toh skip
        if self._setup_done:
            return self.get_response(request)

        # Lazy import to avoid app-registry issues at startup
        try:
            from doctor.models import InnerMember
            owner_exists = InnerMember.objects.filter(is_owner=True).exists()
        except Exception:
            # DB table abhi tak nahi bani (fresh migrate ke pehle) — skip
            return self.get_response(request)

        if owner_exists:
            self._setup_done = True  # Cache kar lo
            return self.get_response(request)

        # Owner nahi hai → Setup wizard pe bhejo
        setup_url = reverse('clinic:setup_clinic')
        return redirect(setup_url)
