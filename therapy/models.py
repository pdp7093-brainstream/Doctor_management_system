from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class Therapy(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    duration_minutes = models.PositiveIntegerField(default=45)
    price_per_session = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['sort_order', 'name']

    def __str__(self):
        return self.name


class PrescriptionTherapy(models.Model):
    FREQUENCY_DAILY = 'daily'
    FREQUENCY_ALTERNATE = 'alternate'
    FREQUENCY_TWICE_WEEK = 'twice_week'
    FREQUENCY_WEEKLY = 'weekly'
    FREQUENCY_CHOICES = [
        (FREQUENCY_DAILY, 'Daily'),
        (FREQUENCY_ALTERNATE, 'Alternate days'),
        (FREQUENCY_TWICE_WEEK, 'Twice a week'),
        (FREQUENCY_WEEKLY, 'Weekly'),
    ]

    prescription = models.ForeignKey(
        'appointment.Prescription',
        related_name='therapies',
        on_delete=models.CASCADE,
    )
    therapy = models.ForeignKey(Therapy, on_delete=models.PROTECT)
    sessions = models.PositiveIntegerField(
        default=7,
        validators=[MinValueValidator(1), MaxValueValidator(60)],
    )
    frequency = models.CharField(
        max_length=20,
        choices=FREQUENCY_CHOICES,
        default=FREQUENCY_DAILY,
    )
    start_date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)
    price_per_session = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        self.price_per_session = self.therapy.price_per_session
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.therapy.name} ({self.sessions} sessions)'