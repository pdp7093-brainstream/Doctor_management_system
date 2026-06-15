from django.shortcuts import redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from .models import InnerMember


def role_required(required_role):
    def decorator(view_func):
        def wrapper(request, *args, **kwargs):

            if not request.user.is_authenticated:
                messages.error(request, "Please login first")
                return redirect('doctor:login')

            try:
                member = InnerMember.objects.get(user=request.user)
            except InnerMember.DoesNotExist:
                messages.error(request, "User role not assigned")
                return redirect('doctor:login')

            if member.role != required_role:

                if member.role == 'biller':
                    return redirect('billing:bill_list')

                return redirect('doctor:dashboard')

            return view_func(request, *args, **kwargs)

        return wrapper
    return decorator


def owner_required(view_func):
    """
    Sirf clinic owner (is_owner=True) ko access deta hai.
    Baki sab — chahe doctor ho ya biller — redirect ho jaate hain.
    """
    def wrapper(request, *args, **kwargs):

        if not request.user.is_authenticated:
            messages.error(request, "Please login first")
            return redirect('doctor:login')

        try:
            member = InnerMember.objects.get(user=request.user)
        except InnerMember.DoesNotExist:
            messages.error(request, "User role not assigned")
            return redirect('doctor:login')

        if not member.is_owner:
            messages.error(request, "Aapke paas yeh page access karne ki permission nahi hai.")
            if member.role == 'biller':
                return redirect('billing:bill_list')
            return redirect('doctor:dashboard')

        return view_func(request, *args, **kwargs)

    return wrapper