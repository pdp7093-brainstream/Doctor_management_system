from django.db import models
from doctor.models import InnerMember,Medicine
from accounts.models import Patient

# Create your models here.
class Appointment(models.Model):
    status_choices = [
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'), 
        ('cancelled', 'Cancelled'),
    ]

    patient = models.ForeignKey(Patient,on_delete=models.CASCADE)
    doctor = models.ForeignKey(InnerMember,on_delete=models.CASCADE,null=True)
    full_name = models.CharField(max_length=100,default="example name")
    phone = models.CharField(max_length=10,default="1234567890")

    appointment_date = models.DateField()   
    time_slot = models.TimeField()
    status = models.CharField(max_length=20, choices=status_choices, default='pending')
    notes = models.TextField(blank=True , null=True)

    create_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


    def __str__(self):
        return f"{self.patient.user.username} - {self.appointment_date} at {self.time_slot}"



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

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Prescription for {self.visit.patient.user.username} on {self.visit.appointment.appointment_date}"

# Prescription list 
class PrescriptionItem(models.Model):
    prescription = models.ForeignKey(Prescription, on_delete=models.CASCADE, related_name="items")

    medicine_variant = models.ForeignKey(   # 🔥 NEW FIELD
        'medicine.MedicineVariant',
        on_delete=models.CASCADE,
        null=True,
        blank=True
    )
    dosage = models.CharField(max_length=100)
    days = models.IntegerField()

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Prescription Item for {self.prescription.visit.patient.user.username} on {self.prescription.visit.appointment.appointment_date}"