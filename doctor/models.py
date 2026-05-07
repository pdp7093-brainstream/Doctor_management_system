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

    def __str__(self):
        return self.user.username
    

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

class ClinicSettings(models.Model):
    doctor = models.OneToOneField('InnerMember', on_delete=models.CASCADE)

    clinic_name = models.CharField(max_length=255)
    clinic_logo = models.ImageField(upload_to='clinic_logo/', null=True, blank=True)

    address = models.TextField()
    phone = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)

    gst_number = models.CharField(max_length=50, blank=True)

    opening_time = models.TimeField(null=True, blank=True)
    closing_time = models.TimeField(null=True, blank=True)
    lunch_start = models.TimeField(null=True, blank=True)
    lunch_end = models.TimeField(null=True, blank=True)

    footer_note = models.TextField(blank=True)

    def __str__(self):
        return self.clinic_name