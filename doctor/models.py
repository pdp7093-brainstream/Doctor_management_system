from django.db import models
from django.contrib.auth.models import User
# Create your models here.

class InnerMember(models.Model):
    ROLE_CHOICES = (
        ('Doctor', 'doctor'),
        ('Biller', 'biller'),
       
    )
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)

    doctor = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='staff'
    )

    def __str__(self):
        return self.user.username
    

