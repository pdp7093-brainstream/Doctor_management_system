from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

from doctor.models import InnerMember


BILLING_TYPE_PACKAGE = 'package'
BILLING_TYPE_PER_SESSION = 'per_session'
BILLING_TYPE_CHOICES = [
    (BILLING_TYPE_PACKAGE, 'Package'),
    (BILLING_TYPE_PER_SESSION, 'Per session'),
]


class Therapy(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    duration_minutes = models.PositiveIntegerField(default=45)
    price_per_session = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    default_billing_type = models.CharField(
        max_length=20,
        choices=BILLING_TYPE_CHOICES,
        default=BILLING_TYPE_PER_SESSION,
    )
    session_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    default_sessions = models.PositiveIntegerField(default=1)
    package_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
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
    billing_type = models.CharField(
        max_length=20,
        choices=BILLING_TYPE_CHOICES,
        blank=True,
        default='',
    )
    total_sessions = models.PositiveIntegerField(
        default=1,
        validators=[MinValueValidator(1), MaxValueValidator(60)],
    )
    session_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    package_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    status = models.CharField(
        max_length=20,
        choices=[('active', 'Active'), ('completed', 'Completed'), ('cancelled', 'Cancelled')],
        default='active',
    )
    package_billed = models.ForeignKey(
        'billing.Bill',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='package_prescriptions',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if not self.billing_type:
            self.billing_type = self.therapy.default_billing_type
        if self.session_price is None:
            self.session_price = self.therapy.session_price
        if self.package_price is None:
            self.package_price = self.therapy.package_price
        if self._state.adding or not self.price_per_session:
            self.price_per_session = self.therapy.price_per_session
        super().save(*args, **kwargs)

    @property
    def sessions_done(self):
        prefetched = getattr(self, '_prefetched_objects_cache', {}).get('session_records')
        if prefetched is not None:
            return sum(session.status == TherapySession.STATUS_DONE for session in prefetched)
        return self.session_records.filter(status=TherapySession.STATUS_DONE).count()

    @property
    def sessions_remaining(self):
        return max(self.total_sessions - self.sessions_done, 0)

    @property
    def progress_text(self):
        return f'{self.sessions_done}/{self.total_sessions}'

    @property
    def progress_percent(self):
        if not self.total_sessions:
            return 0
        return min(int(self.sessions_done * 100 / self.total_sessions), 100)

    def __str__(self):
        return f'{self.therapy.name} ({self.sessions} sessions)'


class TherapySession(models.Model):
    STATUS_DONE = 'done'
    STATUS_MISSED = 'missed'
    STATUS_CHOICES = [(STATUS_DONE, 'Done'), (STATUS_MISSED, 'Missed')]

    prescription_therapy = models.ForeignKey(
        PrescriptionTherapy,
        on_delete=models.CASCADE,
        related_name='session_records',
    )
    session_no = models.PositiveIntegerField()
    date = models.DateField(default=timezone.localdate)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_DONE)
    notes = models.TextField(blank=True)
    done_by = models.ForeignKey(
        InnerMember,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='therapy_sessions_done',
    )
    bill = models.ForeignKey(
        'billing.Bill',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='therapy_sessions',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['session_no']
        constraints = [
            models.UniqueConstraint(
                fields=['prescription_therapy', 'session_no'],
                name='unique_prescribed_therapy_session_no',
            ),
        ]

    def __str__(self):
        return f'{self.prescription_therapy.therapy.name} session {self.session_no}'


class TherapyBillItem(models.Model):
    bill = models.ForeignKey('billing.Bill', on_delete=models.CASCADE, related_name='therapy_items')
    prescription_therapy = models.ForeignKey(
        PrescriptionTherapy,
        on_delete=models.PROTECT,
        related_name='therapy_bill_items',
    )
    therapy_name = models.CharField(max_length=100)
    billing_type = models.CharField(max_length=20, choices=BILLING_TYPE_CHOICES)
    sessions = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['prescription_therapy'],
                condition=models.Q(billing_type=BILLING_TYPE_PACKAGE),
                name='unique_package_bill_item_per_prescribed_therapy',
            ),
        ]

    def __str__(self):
        return f'{self.therapy_name} - {self.get_billing_type_display()}'
