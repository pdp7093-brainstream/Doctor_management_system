from django.contrib import admin

from .models import PrescriptionTherapy, Therapy, TherapyBillItem, TherapySession


@admin.register(Therapy)
class TherapyAdmin(admin.ModelAdmin):
    list_display = ('name', 'duration_minutes', 'price_per_session', 'is_active', 'sort_order')
    list_filter = ('is_active',)
    search_fields = ('name', 'description')
    ordering = ('sort_order', 'name')


@admin.register(PrescriptionTherapy)
class PrescriptionTherapyAdmin(admin.ModelAdmin):
    list_display = ('therapy', 'prescription', 'sessions', 'frequency', 'start_date', 'price_per_session')
    list_filter = ('frequency',)
    search_fields = ('therapy__name', 'prescription__visit__patient__user__username')


@admin.register(TherapySession)
class TherapySessionAdmin(admin.ModelAdmin):
    list_display = ('prescription_therapy', 'session_no', 'date', 'status', 'done_by', 'bill')
    list_filter = ('status', 'date')


@admin.register(TherapyBillItem)
class TherapyBillItemAdmin(admin.ModelAdmin):
    list_display = ('therapy_name', 'billing_type', 'sessions', 'amount', 'bill')
    list_filter = ('billing_type',)