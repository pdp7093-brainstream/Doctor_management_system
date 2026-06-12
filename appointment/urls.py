from django.urls import path
from . import views
from .views import *


app_name = 'appointment'

urlpatterns = [
    path('',Book_appointment.as_view(),name='appointment'),
    path('get-slots/',views.get_slots,name='get_slots'),
    path('search-patients/', views.search_patients, name='search_patients'),
    path('manage_appointments/', Manage_appointments.as_view(), name='manage_appointments'),
    path('add-appointment/', Add_appointment.as_view(), name='add_appointment'),   
    path('cancel-appointment/<str:hid>/',views.cancel_appointment,name='cancel_appointment'),
    path('delete-appointment/<str:hid>/',views.delete_appointment,name='delete_appointment'),
    path('bulk-delete-appointments/', views.bulk_delete_appointments, name='bulk_delete_appointments'),
    
    # Prescription Url 
    path('start-visit/<str:hid>/',StartVisitView.as_view(),name='start_visit'),
    path('prescription/<str:hid>/',PrescriptionView.as_view(),name='prescription'),
    path('prescription/<str:hid>/print/', views.print_prescription, name='print_prescription'),
    path('detail-modal/<str:hid>/', views.appointment_detail_modal, name='appointment_detail_modal'),
    path('appointment/<str:hid>/', views.appointment_detail, name='appointment_detail'),

]