from django.db import models
from doctor.models import InnerMember
from accounts.models import *
from django.contrib.auth.models import User
from accounts.models import Patient, FamilyMember
from .file_validation import clean_original_filename, validate_uploaded_document

class Appointment(models.Model):
    BOOKED_STATUSES = ('pending', 'confirmed', 'completed')

    status_choices = [
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('cancelled', 'Cancelled'),
        ('completed', 'Completed'),
    ]

    patient = models.ForeignKey(Patient, on_delete=models.CASCADE)

    family_member = models.ForeignKey(FamilyMember,on_delete=models.CASCADE,null=True,blank=True)

    doctor = models.ForeignKey(InnerMember,on_delete=models.CASCADE,null=True)

    booked_by = models.ForeignKey(User,on_delete=models.SET_NULL,null=True,blank=True,related_name='booked_appointments')

    appointment_date = models.DateField()
    time_slot = models.TimeField()
    # Consultation type: in-person / phone / video
    CONSULTATION_CHOICES = [
        ('in_person', 'In Person'),
        ('phone', 'Phone'),
        ('video', 'Video'),
    ]
    
    consultation_type = models.CharField(
        max_length=20,
        choices=CONSULTATION_CHOICES,
        default='in_person'
    )
    
    is_archived = models.BooleanField(default=False)
    archived_at = models.DateTimeField(null=True,blank=True)
    status = models.CharField(
        max_length=20,
        choices=status_choices,
        default='pending'
    )

    notes = models.TextField(blank=True, null=True)
    cancellation_reason = models.TextField(blank=True, null=True)

    class Meta:
        indexes = [
            models.Index(fields=['appointment_date', 'time_slot'], name='appt_date_time_idx'),
            models.Index(fields=['appointment_date', 'status'], name='appt_date_status_idx'),
            models.Index(fields=['status'], name='appt_status_idx'),
            models.Index(fields=['doctor', 'appointment_date'], name='appt_doctor_date_idx'),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['doctor', 'appointment_date', 'time_slot'],
                condition=models.Q(
                    is_archived=False,
                    status__in=['pending', 'confirmed', 'completed'],
                ),
                name='unique_active_appointment_slot',
            ),
        ]

    def __str__(self):
        return f"{self.patient.user.username} - {self.appointment_date}"

    @classmethod
    def booked_slots(cls):
        return cls.objects.filter(status__in=cls.BOOKED_STATUSES, is_archived=False)

# Visit Model 
class Visit(models.Model):
    patient = models.ForeignKey(Patient,on_delete=models.CASCADE)
    doctor = models.ForeignKey(InnerMember,on_delete=models.CASCADE,null=True)
    appointment = models.ForeignKey(Appointment,on_delete=models.CASCADE,null=True)

    visted_status = models.CharField(max_length=20, default='in_progress')
    notes = models.TextField(blank=True, null=True)
    symptoms = models.TextField(blank=True, null=True)
    diagnosis = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.patient.user.username} - {self.doctor.user.username} on {self.appointment.appointment_date}"



# Prescription Model 
class Prescription(models.Model):
    visit = models.OneToOneField(Visit, on_delete=models.CASCADE)
    is_stock_deducted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Prescription for {self.visit.patient.user.username} on {self.visit.appointment.appointment_date}"


class LabDocument(models.Model):
    visit = models.ForeignKey(Visit, on_delete=models.CASCADE, related_name='lab_documents')
    file = models.FileField(upload_to='lab_documents/%Y/%m/')
    original_name = models.CharField(max_length=255)
    uploaded_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='uploaded_lab_documents'
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-uploaded_at']

    def clean(self):
        super().clean()
        if self.file:
            self.original_name = clean_original_filename(self.original_name or self.file.name)
            validate_uploaded_document(self.file)

    def __str__(self):
        return f"{self.original_name} - {self.visit.patient.user.username}"


class PatientUploadedDocument(models.Model):
    patient = models.ForeignKey(Patient,on_delete=models.CASCADE,related_name='uploaded_documents')
    family_member = models.ForeignKey(FamilyMember,on_delete=models.SET_NULL,null=True,blank=True,related_name='uploaded_documents')
    file = models.FileField(upload_to='patient_documents/%Y/%m/')
    original_name = models.CharField(max_length=255)
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL,null=True,blank=True,related_name='patient_uploaded_documents')
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-uploaded_at']

    def clean(self):
        super().clean()
        if self.file:
            self.original_name = clean_original_filename(self.original_name or self.file.name)
            validate_uploaded_document(self.file)

    def __str__(self):
        owner = self.family_member.name if self.family_member else (self.patient.user.get_full_name() or self.patient.user.username)
        return f"{self.original_name} - {owner}"

# Prescription list 
class PrescriptionItem(models.Model):
    prescription = models.ForeignKey(Prescription, on_delete=models.CASCADE, related_name="items")

    medicine_variant = models.ForeignKey('medicine.MedicineVariant', on_delete=models.CASCADE, null=True, blank=True)
    dosage = models.CharField(max_length=100)
    days = models.IntegerField()
    notes = models.TextField(blank=True, null=True)
    should_deduct    = models.BooleanField(default=True) 
    was_deducted = models.BooleanField(default=False)
    
    # Billing tracking - tracks which bill this item was included in
    billed_on = models.DateTimeField(null=True, blank=True)  # when the bill was generated
    bill_id = models.IntegerField(null=True, blank=True)  # which bill ID
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Prescription Item for {self.prescription.visit.patient.user.username} on {self.prescription.visit.appointment.appointment_date}"

class PatientOldDocument(models.Model):
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='old_documents')
    family_member = models.ForeignKey(FamilyMember, on_delete=models.SET_NULL, null=True, blank=True, related_name='old_documents')
    file = models.FileField(upload_to='old_patient_data/%Y/%m/')
    original_name = models.CharField(max_length=255)
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='uploaded_old_documents')
    uploaded_at = models.DateTimeField(auto_now_add=True)


    class Meta:
        ordering = ['-uploaded_at']

    def clean(self):
        super().clean()
        if self.file:
            self.original_name = clean_original_filename(self.original_name or self.file.name)
            validate_uploaded_document(self.file)

    def __str__(self):
        owner = self.family_member.name if self.family_member else (self.patient.user.get_full_name() or self.patient.user.username)
        return f"{self.original_name} - {owner} (Old Data)"
