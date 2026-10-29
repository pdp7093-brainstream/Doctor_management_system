from django.shortcuts import redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from .models import InnerMember
from accounts.models import Patient


def _redirect_without_member(request):
    if Patient.objects.filter(user=request.user).exists():
        messages.info(request, "That page is only for clinic staff.")
        return redirect('dashboard')
    messages.warning(request, "Please log in with your account.")
    return redirect('login')


def _redirect_unauthenticated_doctor(request):
    if not request.session.pop("_doctor_logout_redirect", False):
        messages.error(request, "Please login first")
    return redirect('doctor:login')


def role_required(required_role):
    def decorator(view_func):
        def wrapper(request, *args, **kwargs):

            if not request.user.is_authenticated:
                return _redirect_unauthenticated_doctor(request)

            try:
                member = InnerMember.objects.get(user=request.user)
            except InnerMember.DoesNotExist:
                return _redirect_without_member(request)

            if member.role != required_role:

                if member.role == 'biller':
                    return redirect('billing:bill_list')

                return redirect('doctor:dashboard')

            return view_func(request, *args, **kwargs)

        return wrapper
    return decorator


def owner_required(view_func):
    """
    Allows access only to the clinic owner (member.is_owner == True).
    All other roles (doctor, biller) are redirected.
    """
    def wrapper(request, *args, **kwargs):

        if not request.user.is_authenticated:
            return _redirect_unauthenticated_doctor(request)

        try:
            member = InnerMember.objects.get(user=request.user)
        except InnerMember.DoesNotExist:
            return _redirect_without_member(request)

        if not member.is_owner:
            messages.error(request, "You do not have permission to access this page.")
            if member.role == 'biller':
                return redirect('billing:bill_list')
            return redirect('doctor:dashboard')

        return view_func(request, *args, **kwargs)

    return wrapper
