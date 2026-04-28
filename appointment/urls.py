from django.urls import path
from . import views
from .views import *

app_name = 'appointment'
urlpatterns = [
    path('',views.appointment,name='appointment'),

    path('manage_appointments/', Manage_appointments.as_view(), name='manage_appointments'),
    path('add-appointment/', Add_appointment.as_view(), name='add_appointment'),
    
]