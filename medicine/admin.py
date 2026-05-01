from django.contrib import admin
from .models import Medicine, MedicineVariant
# Register your models here.

class MedicineVariantInline(admin.TabularInline):
    model = MedicineVariant
    extra =1 

@admin.register(Medicine)
class MedicineAdmin(admin.ModelAdmin):
    list_display = ['name','short_name','medicine_type','company','is_active']
    search_fields = ['name','short_name','company']
    list_filter = ['medicine_type','is_active']
    inlines = [MedicineVariantInline]


@admin.register(MedicineVariant)
class MedicineVariantAdmin(admin.ModelAdmin):
    list_display = ['medicine','power','price','stock','is_low_stock']
    search_fields = ['medicine__name','medicine__short_name']