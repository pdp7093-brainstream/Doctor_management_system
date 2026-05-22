from django.shortcuts import redirect
from django.contrib import messages


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

    