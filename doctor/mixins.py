from django.shortcuts import redirect
from django.contrib import messages
from django.http import HttpResponseForbidden
from .models import InnerMember


def has_staff_access(user):
    return user.is_superuser or InnerMember.objects.filter(user=user).exists()


class StaffRequiredMixin:
    def dispatch(self, request, *args, **kwargs):
        if has_staff_access(request.user):
            return super().dispatch(request, *args, **kwargs)
        if (
            request.method == 'POST'
            or request.headers.get('x-requested-with') == 'XMLHttpRequest'
        ):
            return HttpResponseForbidden()
        return redirect('dashboard')


class BillingAccessMixin:
    allowed_roles = []
    def dispatch(self, request, *args, **kwargs):

        try:
            member = request.user.innermember

            # Allow only doctor and biller
            if member.role not in ['doctor', 'biller']:

                messages.error(request, "Access denied.")
                return redirect('doctor:login')

        except Exception:

            messages.error(request, "Access denied.")
            return redirect('doctor:login')

        return super().dispatch(request, *args, **kwargs)

class ExpenseAccessMixin(BillingAccessMixin):
    allowed_roles = ['doctor', 'biller']

    