from django.contrib import admin
from .models import *
# Register your models here.

class BillItemInline(admin.TabularInline):
    model = BillItem
    extra = 0

@admin.register(Bill)
class BillAdmin(admin.ModelAdmin):
    list_display = ('bill_number', 'visit', 'bill_date', 'total', 'payment_status')
    list_filter = ('payment_status', 'bill_date')
    search_fields = ('bill_number', 'visit__patient__user__first_name', 'visit__patient__user__last_name')
    inlines = [BillItemInline]

    