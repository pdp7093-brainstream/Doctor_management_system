import os

from django.conf import settings
from django.http import FileResponse, Http404
from django.shortcuts import redirect, render


def protected_media(request, path):
    if not path or path.startswith('/') or '..' in path:
        raise Http404

    path = path.replace('\\', '/')
    path_parts = path.split('/')
    if any(part in ('', '.', '..') for part in path_parts):
        raise Http404

    media_type = path_parts[0]
    protected_types = {'lab_documents', 'patient_documents', 'old_patient_data'}
    login_required_types = {'profile_pictures', 'staff'}
    public_types = {'clinic', 'clinic_logo'}

    if media_type not in protected_types | login_required_types | public_types | {'patients'}:
        raise Http404

    if media_type == 'patients':
        if len(path_parts) < 3:
            raise Http404
        patient_id = path_parts[1].split('_', 1)[0]
        try:
            patient_id = int(patient_id)
        except ValueError:
            raise Http404

        if not request.user.is_authenticated:
            return redirect('login')

        from accounts.models import Patient
        from doctor.models import InnerMember

        is_staff_or_member = (
            request.user.is_staff
            or request.user.is_superuser
            or InnerMember.objects.filter(
                user=request.user, role__in=('doctor', 'biller')
            ).exists()
        )
        is_patient_owner = Patient.objects.filter(
            pk=patient_id, user=request.user
        ).exists()
        if not is_staff_or_member and not is_patient_owner:
            raise Http404

    if media_type == 'staff' and (
        len(path_parts) < 4 or path_parts[2] != 'profile'
    ):
        raise Http404

    if media_type not in public_types and not request.user.is_authenticated:
        return redirect('login')

    if media_type in protected_types:
        from appointment.models import LabDocument, PatientOldDocument, PatientUploadedDocument
        from doctor.models import InnerMember

        if media_type == 'lab_documents':
            document = LabDocument.objects.filter(file=path).select_related(
                'visit__patient'
            ).first()
            patient = document.visit.patient if document else None
        elif media_type == 'patient_documents':
            document = PatientUploadedDocument.objects.filter(file=path).select_related(
                'patient'
            ).first()
            patient = document.patient if document else None
        else:
            document = PatientOldDocument.objects.filter(file=path).select_related(
                'patient'
            ).first()
            patient = document.patient if document else None

        if not document:
            raise Http404

        is_staff_or_doctor = (
            request.user.is_staff
            or request.user.is_superuser
            or InnerMember.objects.filter(user=request.user, role='doctor').exists()
        )
        if not is_staff_or_doctor and patient.user_id != request.user.pk:
            raise Http404

        try:
            media_file = document.file.open('rb')
        except (FileNotFoundError, OSError, ValueError):
            raise Http404
    else:
        media_path = os.path.join(settings.MEDIA_ROOT, path)
        try:
            if not os.path.isfile(media_path):
                raise Http404
            media_file = open(media_path, 'rb')
        except (FileNotFoundError, OSError, ValueError):
            raise Http404

    return FileResponse(media_file, filename=path_parts[-1])


def custom_404(request, exception):
    """Custom 404 - Page Not Found"""
    return render(request, '404.html', status=404)


def custom_500(request):
    """Custom 500 - Server Error"""
    return render(request, '500.html', status=500)


def custom_403(request, exception):
    """Custom 403 - Forbidden"""
    return render(request, '403.html', status=403)
