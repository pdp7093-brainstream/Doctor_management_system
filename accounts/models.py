from django.db import models
from django.contrib.auth.models import User
# Create your models here.


class Patient(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    phone = models.CharField(max_length=15, blank=True)
    address = models.TextField(blank=True, null=True)
    
    # In teeno fields mein null=True aur blank=True add karein
    dob = models.DateField(null=True, blank=True)
    gender = models.CharField(max_length=20, null=True, blank=True)
    bld_grop = models.CharField(max_length=10, null=True, blank=True)
    
    # Profile Picture Field
    profile_picture = models.ImageField(upload_to='profile_pictures/', null=True, blank=True, default='profile_pictures/default-avatar.png')

    def __str__(self):
        return self.user.username
    
class FamilyMember(models.Model):
    GENDER_CHOICES = [
        ('male', 'Male'),
        ('female', 'Female'),
        ('other', 'Other'),
    ]
    BLOOD_GROUP_CHOICES = [
        ('A+', 'A+'), ('A-', 'A-'),
        ('B+', 'B+'), ('B-', 'B-'),
        ('O+', 'O+'), ('O-', 'O-'),
        ('AB+', 'AB+'), ('AB-', 'AB-'),
    ]

    patient   = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name="members")
    name      = models.CharField(max_length=100)
    relation  = models.CharField(max_length=50)
    phone     = models.CharField(max_length=15, blank=True)
    gender    = models.CharField(max_length=10, choices=GENDER_CHOICES, null=True, blank=True)
    dob       = models.DateField(null=True, blank=True)
    bld_grop  = models.CharField(max_length=10, choices=BLOOD_GROUP_CHOICES, null=True, blank=True)

    class Meta:
        # Same patient ke liye same name+relation duplicate nahi hoga
        unique_together = ('patient', 'name', 'relation')

    def __str__(self):
        return f"{self.name} ({self.relation})"