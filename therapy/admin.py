from django.contrib import admin

from .models import PrescriptionTherapy, Therapy


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