from django.db import models
from datetime import date

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

    cost_price = models.DecimalField(max_digits=8, decimal_places=2)
    selling_price = models.DecimalField(max_digits=8, decimal_places=2,default=0)

    stock = models.PositiveIntegerField(default=0)

    UNIT_CHOICES = [
        ('piece', 'Piece'),
        ('ml', 'ML'),
        ('gm', 'Gram'),
    ]
    unit = models.CharField(max_length=10, choices=UNIT_CHOICES, default='piece')

    unit_per_strip = models.IntegerField(null=True, blank=True)

    low_stock_alert = models.PositiveIntegerField(default=10)

    mfg_date = models.DateField(null=True, blank=True)
    exp_date = models.DateField(null=True, blank=True)

    def __str__(self):
        return f"{self.medicine.short_name} - {self.power}"

    @property
    def is_low_stock(self):
        return self.stock <= self.low_stock_alert

    @property
    def is_expired(self):
        return self.exp_date and self.exp_date < date.today()

    # ------------------------------------------------------------------
    # Strip / unit computed properties (no extra DB fields)
    # ------------------------------------------------------------------

    @property
    def stock_breakdown(self):
        """
        Dynamically calculate strips and remaining loose units from stock.

        Returns:
            dict: {"strips": int, "remaining_units": int}
                  If unit_per_strip is 0 or None the entire stock is treated
                  as loose units (strips = 0) to avoid ZeroDivisionError.
        """
        ups = self.unit_per_strip  # units per strip
        if not ups:  # handles None and 0
            return {"strips": 0, "remaining_units": self.stock}
        return {
            "strips": self.stock // ups,
            "remaining_units": self.stock % ups,
        }

    @property
    def stock_display(self):
        """
        Human-readable stock string, e.g.  '10 strips'  or  '9 strips 5 tablets'.

        Returns:
            str: formatted stock string
        """
        breakdown = self.stock_breakdown
        strips = breakdown["strips"]
        remaining = breakdown["remaining_units"]
        unit_label = self.get_unit_display().lower()  # 'piece', 'ml', 'gram' …

        if strips and remaining:
            return f"{strips} strip{'s' if strips != 1 else ''} {remaining} {unit_label}{'s' if remaining != 1 else ''}"
        if strips:
            return f"{strips} strip{'s' if strips != 1 else ''}"
        return f"{remaining} {unit_label}{'s' if remaining != 1 else ''}"

    def strips_to_units(self, strips: int) -> int:
        """
        Convert a number of strips into individual units.

        Usage example:
            variant.strips_to_units(5)  →  50  (if unit_per_strip = 10)

        Args:
            strips (int): number of strips to convert

        Returns:
            int: total units; 0 when unit_per_strip is not set
        """
        ups = self.unit_per_strip or 0
        return strips * ups
    
class Vendor(models.Model):
    name = models.CharField(max_length=255)
    phone = models.CharField(max_length=10,blank=True,null=True)
    email = models.EmailField(blank=True,null=True)
    address = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.name
    

class Purchase(models.Model):
    vendor = models.ForeignKey(Vendor, on_delete = models.CASCADE)
    date = models.DateField(auto_now_add = True)
    total_amount = models.FloatField(default=0)

    status_choices = [
    ('draft', 'Draft'),
    ('ordered', 'Ordered'),
    ('received', 'Received'),
    ]

    status = models.CharField(max_length=20, choices=status_choices, default='ordered',null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True,null=True, blank=True)


class PurchaseItem(models.Model):
    purchase = models.ForeignKey(Purchase, on_delete = models.CASCADE,related_name = "items")
    medicine_variant = models.ForeignKey(MedicineVariant, on_delete = models.CASCADE)

    quantity_strips = models.IntegerField()
    unit_per_strip = models.IntegerField()

    #Price 
    strip_price = models.DecimalField(max_digits =10, decimal_places = 2, default = 0)
    tax_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    #Calculated prices (saved so you don't have to compute them at query time)

    total_units = models.IntegerField(default=0)
    final_amount = models.DecimalField(max_digits = 12,decimal_places = 2, default =0)
    effective_unit_cost = models.DecimalField(max_digits=10,decimal_places = 2,default=0)

    
