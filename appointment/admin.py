from django.contrib import admin
from .models import (
    Appointment, Visit, Prescription, PrescriptionItem, LabDocument, PatientUploadedDocument
)

# Register your models here.

@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = ('patient', 'doctor', 'appointment_date', 'status')
    list_filter = ('status', 'appointment_date')
    search_fields = ('patient__user__first_name', 'patient__user__last_name', 'doctor__user__first_name')


@admin.register(Visit)
class VisitAdmin(admin.ModelAdmin):
    list_display = ('patient', 'doctor', 'created_at', 'visted_status')
    list_filter = ('visted_status', 'created_at')
    search_fields = ('patient__user__first_name', 'doctor__user__first_name')


@admin.register(Prescription)
class PrescriptionAdmin(admin.ModelAdmin):
    list_display = ('visit', 'is_stock_deducted', 'created_at')
    list_filter = ('is_stock_deducted', 'created_at')
    search_fields = ('visit__patient__user__first_name',)


@admin.register(PrescriptionItem)
class PrescriptionItemAdmin(admin.ModelAdmin):
    list_display = ('prescription', 'medicine_variant', 'dosage', 'days')
    search_fields = ('prescription__visit__patient__user__first_name',)


@admin.register(LabDocument)
class LabDocumentAdmin(admin.ModelAdmin):
    list_display = ('original_name', 'visit', 'uploaded_by', 'uploaded_at')
    list_filter = ('uploaded_at',)
    search_fields = ('original_name', 'visit__patient__user__first_name')


@admin.register(PatientUploadedDocument)
class PatientUploadedDocumentAdmin(admin.ModelAdmin):
    list_display = ('original_name', 'patient', 'uploaded_by', 'uploaded_at')
    list_filter = ('uploaded_at',)
    search_fields = ('original_name', 'patient__user__first_name')


