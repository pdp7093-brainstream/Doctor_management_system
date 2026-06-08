from django.db import models
from appointment.models import Visit
from medicine.models import MedicineVariant


class BillSequence(models.Model):
    name = models.CharField(max_length=32, primary_key=True)
    last_number = models.PositiveIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    @classmethod
    def next_bill_number(cls):
        from django.db import transaction

        with transaction.atomic():
            sequence, _ = cls.objects.select_for_update().get_or_create(
                name='bill_numbers',
                defaults={'last_number': 0},
            )
            sequence.last_number += 1
            sequence.save(update_fields=['last_number', 'updated_at'])
            return f'BILL-{sequence.last_number:04d}'

    def __str__(self):
        return f'{self.name}: {self.last_number}'


class Bill(models.Model):

    PAYMENT_METHOD = [
        ('cash', 'Cash'),
        ('card', 'Card'),
        ('upi', 'UPI'),
        ('online', 'Online'),
    ]

    PAYMENT_STATUS = [
        ('unpaid', 'Unpaid'),
        ('paid', 'Paid'),
        ('partial', 'Partial'),
    ]

    visit          = models.ForeignKey(
        Visit, on_delete=models.CASCADE, related_name='bills'
    )
    bill_number    = models.CharField(max_length=20, unique=True)
    
    # Addon bill tracking
    is_addon = models.BooleanField(default=False)  # True = this is an addon/amendment bill
    parent_bill = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='addons'
    )  # Reference to the original bill
    
    bill_date      = models.DateField(auto_now_add=True)
    consultation_fee = models.DecimalField(max_digits=10,decimal_places=2,default=0)
    subtotal       = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    gst_percent    = models.DecimalField(max_digits=5, decimal_places=2, default=18)
    gst_amount     = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    discount       = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total          = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    payment_method = models.CharField(
        max_length=10, choices=PAYMENT_METHOD, default='cash'
    )
    payment_status = models.CharField(
        max_length=10, choices=PAYMENT_STATUS, default='unpaid'
    )

    notes          = models.TextField(blank=True, null=True)
    is_archived    = models.BooleanField(default=False)
    archived_at    = models.DateTimeField(null=True, blank=True)
    created_at     = models.DateTimeField(auto_now_add=True)
    updated_at     = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        from decimal import Decimal
        
        # GST + Total calculate
        self.gst_amount = (self.subtotal * self.gst_percent) / Decimal('100')
        self.total = self.consultation_fee + self.subtotal + self.gst_amount - self.discount

        # Bill number auto generate with a locked sequence row.
        if not self.bill_number:
            self.bill_number = BillSequence.next_bill_number()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.bill_number} - {self.visit.patient.user.get_full_name()}"


class BillItem(models.Model):
    bill             = models.ForeignKey(
        Bill, on_delete=models.CASCADE, related_name='items'
    )
    medicine_variant = models.ForeignKey(
        MedicineVariant, on_delete=models.SET_NULL,
        null=True, blank=True
    )
    medicine_name    = models.CharField(max_length=200)  # snapshot
    power            = models.CharField(max_length=50)   # snapshot
    quantity         = models.PositiveIntegerField(default=0)
    unit_price       = models.DecimalField(max_digits=8, decimal_places=2)
    total_price      = models.DecimalField(max_digits=10, decimal_places=2)

    def save(self, *args, **kwargs):
        self.total_price = self.quantity * self.unit_price
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.medicine_name} x{self.quantity}"
