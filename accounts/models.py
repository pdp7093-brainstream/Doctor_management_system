from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

class Patient(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    phone = models.CharField(max_length=15, blank=True, null=True, unique=True)  # ← Phone here (UNIQUE)
    address = models.TextField(blank=True, null=True)
    dob = models.DateField(null=True, blank=True)
    gender = models.CharField(max_length=20, null=True, blank=True)
    bld_grop = models.CharField(max_length=10, null=True, blank=True)
    profile_picture = models.ImageField(
        upload_to='profile_pictures/', 
        null=True, 
        blank=True, 
        default='profile_pictures/default-avatar.png'
    )
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.get_full_name or self.user.email} - {self.phone}"


# Signal: Jab naya User create ho toh Patient auto-create ho
@receiver(post_save, sender=User)
def create_patient(sender, instance, created, **kwargs):
    if created:
        Patient.objects.get_or_create(user=instance)

@receiver(post_save, sender=User)
def save_patient(sender, instance, **kwargs):
    if hasattr(instance, 'patient'):
        instance.patient.save()


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
    phone     = models.CharField(max_length=15, blank=True, null=True)
    gender    = models.CharField(max_length=10, choices=GENDER_CHOICES, null=True, blank=True)
    dob       = models.DateField(null=True, blank=True)
    bld_grop  = models.CharField(max_length=10, choices=BLOOD_GROUP_CHOICES, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True)

    class Meta:
        unique_together = ('patient', 'name', 'relation')

    def __str__(self):
        return f"{self.name} ({self.relation})"