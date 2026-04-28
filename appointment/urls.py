from django.urls import path
from . import views
from .views import *

app_name = 'appointment'
urlpatterns = [
    path('',Book_appointment.as_view(),name='appointment'),
    path('get-slots/',views.get_slots,name='get_slots'),
    path('manage_appointments/', Manage_appointments.as_view(), name='manage_appointments'),
    path('add-appointment/', Add_appointment.as_view(), name='add_appointment'),   
]