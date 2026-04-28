from django.db import models
from django.contrib.auth.models import User
from doctor.models import InnerMember
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
