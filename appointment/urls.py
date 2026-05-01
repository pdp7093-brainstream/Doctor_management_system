from django.urls import path
from . import views
from .views import *

app_name = 'appointment'
urlpatterns = [
    path('',Book_appointment.as_view(),name='appointment'),
    path('get-slots/',views.get_slots,name='get_slots'),
    path('manage_appointments/', Manage_appointments.as_view(), name='manage_appointments'),
    path('add-appointment/', Add_appointment.as_view(), name='add_appointment'),   

    # Prescription Url 
    path('start-visit/<int:appointment_id>/',StartVisitView.as_view(),name='start_visit'),
    path('prescription/<int:visit_id>/',PrescriptionView.as_view(),name='prescription'),
    path('appointment/<int:id>/', views.appointment_detail, name='appointment_detail'),
]