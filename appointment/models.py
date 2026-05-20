from django.db import models
from doctor.models import InnerMember,Medicine
from accounts.models import *

# Create your models here.

from django.contrib.auth.models import User

from accounts.models import Patient, FamilyMember
from doctor.models import InnerMember

class Appointment(models.Model):
    BOOKED_STATUSES = ('pending', 'confirmed', 'completed')

    status_choices = [
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('cancelled', 'Cancelled'),
        ('completed', 'Completed'),
    ]

    patient = models.ForeignKey(Patient, on_delete=models.CASCADE)

    family_member = models.ForeignKey(
        FamilyMember,
        on_delete=models.CASCADE,
        null=True,
        blank=True
    )

    doctor = models.ForeignKey(
        InnerMember,
        on_delete=models.CASCADE,
        null=True
    )

    booked_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='booked_appointments'
    )

    appointment_date = models.DateField()
    time_slot = models.TimeField()

    status = models.CharField(
        max_length=20,
        choices=status_choices,
        default='pending'
    )

    notes = models.TextField(blank=True, null=True)

    class Meta:
        indexes = [
            models.Index(fields=['appointment_date', 'time_slot'], name='appt_date_time_idx'),
            models.Index(fields=['appointment_date', 'status'], name='appt_date_status_idx'),
            models.Index(fields=['status'], name='appt_status_idx'),
            models.Index(fields=['doctor', 'appointment_date'], name='appt_doctor_date_idx'),
        ]

    def __str__(self):
        return f"{self.patient.user.username} - {self.appointment_date}"

    @classmethod
    def booked_slots(cls):
        return cls.objects.filter(status__in=cls.BOOKED_STATUSES)

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

# # Medicine 
# class Medicine(models.Model):
#     name = models.CharField(max_length=255)

#     def __str__(self):
#         return self.name


# Prescription Model 
class Prescription(models.Model):
    visit = models.OneToOneField(Visit, on_delete=models.CASCADE)
    is_stock_deducted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Prescription for {self.visit.patient.user.username} on {self.visit.appointment.appointment_date}"

# Prescription list 
class PrescriptionItem(models.Model):
    prescription = models.ForeignKey(Prescription, on_delete=models.CASCADE, related_name="items")

    medicine_variant = models.ForeignKey(   
        'medicine.MedicineVariant',
        on_delete=models.CASCADE,
        null=True,
        blank=True
    )
    dosage = models.CharField(max_length=100)
    days = models.IntegerField()
    should_deduct    = models.BooleanField(default=True) 
    was_deducted = models.BooleanField(default=False)
    
    # Billing tracking - यह track करता है कि item किस bill में शामिल हुआ
    billed_on = models.DateTimeField(null=True, blank=True)  # जब bill बना
    bill_id = models.IntegerField(null=True, blank=True)  # कौन सा bill
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Prescription Item for {self.prescription.visit.patient.user.username} on {self.prescription.visit.appointment.appointment_date}"
    
