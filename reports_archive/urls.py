from django.urls import path
from . import views

app_name = 'reports_archive'

urlpatterns = [

    path('export/',views.ExportDataView.as_view(),name='export_data'),

    path('archive/',views.ArchiveRecordsView.as_view(),name='archive_records'),

    path('archived-appointments/', views.ArchivedAppointmentsView.as_view(), name='archived_appointments'),

    path(
        'archived-appointments/<int:appointment_id>/restore/',
        views.RestoreAppointmentView.as_view(),
        name='restore_appointment',
    ),

    path('archived-bills/', views.ArchivedBillsView.as_view(), name='archived_bills'),

    path(
        'archived-bills/<int:bill_id>/restore/',
        views.RestoreBillView.as_view(),
        name='restore_bill',
    ),

    path('archived-expenses/', views.ArchivedExpensesView.as_view(), name='archived_expenses'),

    path(
        'archived-expenses/<int:expense_id>/restore/',
        views.RestoreExpenseView.as_view(),
        name='restore_expense',
    ),

]
