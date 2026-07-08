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
    is_owner = models.BooleanField(default=False, help_text='Clinic owner / main doctor — only they can view Clinic Settings')
    phone  = models.CharField(max_length=15, blank=True, default='') 
    profile_picture = models.ImageField(upload_to='profile_pictures/', blank=True, null=True)

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

    def covers_time_slot(self, time_slot):
        from clinic.models import ClinicSettings
        clinic = ClinicSettings.get()
        if self.leave_type == 'full_day':
            return True
        if self.leave_type == 'first_half' and clinic.lunch_start and time_slot < clinic.lunch_start:
            return True
        if self.leave_type == 'second_half' and clinic.lunch_start and time_slot >= clinic.lunch_start:
            return True
        return False

    def get_error_message(self):
        if self.leave_type == 'full_day':
            return "Doctor is on leave on this date."
        return "Doctor is on leave during this time."
    

# When an InnerMember is deleted we usually want to remove the related auth `User` as
# well (so there are no leftover accounts). Add a post_delete signal that deletes
# the `User` only if it still exists — this avoids trying to delete the `User` when
# the deletion originated from the `User` itself (which would already have removed
# the InnerMember via cascade).
from django.db.models.signals import post_delete
from django.dispatch import receiver


@receiver(post_delete, sender=InnerMember)
def _delete_user_with_inner_member(sender, instance, **kwargs):
    """Delete the related User when an InnerMember is removed.

    Uses a queryset delete after checking existence to avoid errors when the
    User has already been removed as part of a parent cascade.
    """
    user_id = getattr(instance, 'user_id', None)
    if not user_id:
        return
    from django.contrib.auth import get_user_model
    UserModel = get_user_model()
    try:
        qs = UserModel.objects.filter(pk=user_id)
        if qs.exists():
            qs.delete()
    except Exception:
        # Be defensive: do not let signal failures break the deletion flow.
        pass


