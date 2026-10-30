from django.utils.text import slugify


def patient_folder(patient):
    slug = slugify(patient.user.get_full_name() or patient.user.username)[:30].strip('-')
    folder_name = f'{patient.id}_{slug}' if slug else str(patient.id)
    return f'patients/{folder_name}'


def member_folder(member):
    slug = slugify(member.name)[:30].strip('-')
    folder_name = f'{member.id}_{slug}' if slug else str(member.id)
    return f'family/{folder_name}'


def patient_profile_picture_upload_path(patient, filename):
    return f'{patient_folder(patient)}/profile/{filename}'


def patient_uploaded_document_upload_path(document, filename):
    folder = patient_folder(document.patient)
    if document.family_member:
        folder = f'{folder}/{member_folder(document.family_member)}'
    return f'{folder}/documents/{filename}'


def patient_old_document_upload_path(document, filename):
    folder = patient_folder(document.patient)
    if document.family_member:
        folder = f'{folder}/{member_folder(document.family_member)}'
    return f'{folder}/old_data/{filename}'


def lab_document_upload_path(document, filename):
    return f'{patient_folder(document.visit.patient)}/lab/{filename}'


def staff_profile_picture_upload_path(member, filename):
    return f'staff/{member.user.id}/profile/{filename}'