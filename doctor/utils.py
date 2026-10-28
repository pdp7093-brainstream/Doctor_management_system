from .models import InnerMember


def get_default_doctor():
    doctor = InnerMember.objects.filter(
        role='doctor',
        is_default_doctor=True,
    ).select_related('user').first()
    if doctor:
        return doctor
    return InnerMember.objects.filter(
        role='doctor',
        user__is_active=True,
    ).select_related('user').order_by('pk').first()