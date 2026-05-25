from django.db import models
from django.contrib.auth.models import User
# Create your models here.

class InnerMember(models.Model):
    ROLE_CHOICES = (
        ('doctor', 'doctor'),
        ('biller', 'biller'),
       
    )
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    phone  = models.CharField(max_length=15, blank=True, default='') 

    doctor = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='staff'
    )

    def get_full_name(self):
        return f"{self.user.first_name} {self.user.last_name}"

    def __str__(self):
        return self.user.username

class DoctorLeave(models.Model):
    LEAVE_CHOICES = [
        ('first_half', 'First Half'),
        ('second_half', 'Second Half'),
        ('full_day', 'Full Day'),
    ]
    doctor = models.ForeignKey('InnerMember', on_delete=models.CASCADE)
    date = models.DateField()
    leave_type = models.CharField(max_length=20, choices=LEAVE_CHOICES)
    reason = models.TextField(blank=True, null=True)

    class Meta:
        unique_together = ('doctor', 'date')

    def __str__(self):
        return f"{self.doctor.user.first_name} - {self.date} ({self.get_leave_type_display()})"
    

# Medicine Model
class Medicine(models.Model):
    name = models.CharField(max_length=100)
    stock = models.IntegerField(default=0)
    price = models.FloatField(default=0)

    mfg_date = models.DateField()
    expiry_date = models.DateField()


    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return self.name

