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
    path('cancel-appointment/<int:appointment_id>/',views.cancel_appointment,name='cancel_appointment'),
    path('delete-appointment/<int:appointment_id>/',views.delete_appointment,name='delete_appointment'),
    
    # Prescription Url 
    path('start-visit/<int:appointment_id>/',StartVisitView.as_view(),name='start_visit'),
    path('prescription/<int:visit_id>/',PrescriptionView.as_view(),name='prescription'),
    path('detail-modal/<int:id>/', views.appointment_detail_modal, name='appointment_detail_modal'),
    path('appointment/<int:id>/', views.appointment_detail, name='appointment_detail'),

]