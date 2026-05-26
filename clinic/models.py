from django.db import models

class ClinicSettings(models.Model):

    SLOT_DURATION_CHOICES = [
        (10, '10 Minutes'),
        (15, '15 Minutes'),
        (20, '20 Minutes'),
        (30, '30 Minutes'),
        (45, '45 Minutes'),
        (60, '1 Hour'),
    ]

    WORKING_DAYS_CHOICES = [
        ('mon', 'Monday'),
        ('tue', 'Tuesday'),
        ('wed', 'Wednesday'),
        ('thu', 'Thursday'),
        ('fri', 'Friday'),
        ('sat', 'Saturday'),
        ('sun', 'Sunday'),
    ]

    # ── Clinic Info ──────────────────────────────────────────
    clinic_name    = models.CharField(max_length=200, default='MediCare Clinic')
    tagline        = models.CharField(max_length=300, blank=True, null=True)
    logo           = models.ImageField(upload_to='clinic/', blank=True, null=True)
    address        = models.TextField(blank=True, null=True)
    city           = models.CharField(max_length=100, blank=True, null=True)
    state          = models.CharField(max_length=100, blank=True, null=True)
    pincode        = models.CharField(max_length=10, blank=True, null=True)
    phone          = models.CharField(max_length=15, blank=True, null=True)
    email          = models.EmailField(blank=True, null=True)
    website        = models.URLField(blank=True, null=True)

    # ── Doctor Info ──────────────────────────────────────────
    doctor_name        = models.CharField(max_length=200, blank=True, null=True)
    specialization     = models.CharField(max_length=200, blank=True, null=True)
    qualification      = models.CharField(max_length=200, blank=True, null=True)
    registration_no    = models.CharField(max_length=100, blank=True, null=True)

    # ── Schedule Settings ────────────────────────────────────
    start_time     = models.TimeField(default='09:00')
    end_time       = models.TimeField(default='18:00')
    slot_duration  = models.IntegerField(
        choices=SLOT_DURATION_CHOICES, default=30
    )
    lunch_start    = models.TimeField(default='13:00')
    lunch_end      = models.TimeField(default='14:00')

    # Working days — store as comma separated string
    # e.g. "mon,tue,wed,thu,fri,sat"
    working_days   = models.CharField(
        max_length=50,
        default='mon,tue,wed,thu,fri,sat'
    )

    # ── Bill Settings ────────────────────────────────────────
    default_gst        = models.DecimalField(
        max_digits=5, decimal_places=2, default=18
    )
    default_consultation_fee = models.DecimalField(
        max_digits=8, decimal_places=2, default=0
    )
    phone_consultation_fee = models.DecimalField(
        max_digits=8, decimal_places=2, default=0
    )
    video_consultation_fee = models.DecimalField(
        max_digits=8, decimal_places=2, default=0
    )
    bill_prefix        = models.CharField(max_length=10, default='BILL')
    bill_footer_note   = models.CharField(
        max_length=300,
        default='Thank you for visiting our clinic.',
        blank=True
    )

    # ── System ───────────────────────────────────────────────
    updated_at     = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = 'Clinic Settings'
        verbose_name_plural = 'Clinic Settings'

    def __str__(self):
        return self.clinic_name

    def save(self, *args, **kwargs):
        # Singleton — sirf ek record hoga
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def get(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def get_working_days_list(self):
        return self.working_days.split(',') if self.working_days else []

    def is_working_day(self, day_str):
        # day_str = 'mon', 'tue' etc.
        return day_str in self.get_working_days_list()