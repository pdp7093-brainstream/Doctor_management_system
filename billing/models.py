from django.db import models
from appointment.models import Visit
from medicine.models import MedicineVariant


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

    visit          = models.OneToOneField(
        Visit, on_delete=models.CASCADE, related_name='bill'
    )
    bill_number    = models.CharField(max_length=20, unique=True)
    bill_date      = models.DateField(auto_now_add=True)

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
    created_at     = models.DateTimeField(auto_now_add=True)
    updated_at     = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        # Bill number auto generate
        if not self.bill_number:
            last = Bill.objects.order_by('-id').first()
            next_id = (last.id + 1) if last else 1
            self.bill_number = f'BILL-{next_id:04d}'

        # GST + Total calculate
        from decimal import Decimal
        self.gst_amount = (self.subtotal * self.gst_percent) / Decimal('100')
        self.total = self.subtotal + self.gst_amount - self.discount
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