from django.db import models

class Medicine(models.Model):

    MEDICINE_TYPE = [
        ('tablet', 'Tablet'),
        ('syrup', 'Syrup'),
        ('injection', 'Injection'),
        ('capsule', 'Capsule'),
        ('drops', 'Drops'),
        ('cream', 'Cream'),
    ]

    name = models.CharField(max_length=200)
    short_name = models.CharField(max_length=50, unique=True)
    medicine_type = models.CharField(max_length=20, choices=MEDICINE_TYPE)
    company = models.CharField(max_length=200, blank=True)
    description = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.short_name})"


class MedicineVariant(models.Model):
    medicine = models.ForeignKey(
        Medicine,
        on_delete=models.CASCADE,
        related_name='variants'
    )
    power = models.CharField(max_length=50)
    price = models.DecimalField(max_digits=8, decimal_places=2)
    stock = models.PositiveIntegerField(default=0)
    low_stock_alert = models.PositiveIntegerField(default=10)

    def __str__(self):
        return f"{self.medicine.short_name} - {self.power}"

    @property
    def is_low_stock(self):
        return self.stock <= self.low_stock_alert