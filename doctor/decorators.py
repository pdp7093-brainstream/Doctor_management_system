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
                messages.error(request, "Unauthorized access")
                return redirect('doctor:login')

            return view_func(request, *args, **kwargs)

        return wrapper
    return decorator