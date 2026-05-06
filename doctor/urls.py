from django.urls import path
from . import views
from .views import *
from medicine.views import *

app_name = 'doctor'

urlpatterns = [
    path('login/',views.login_view,name='login'),  
    path('logout/',views.logout_view,name='logout'),
    path('dashboard/',DashboardView.as_view(),name='dashboard'),
    path('manage-patients/',views.manage_patients,name='manage_patients'),

    path('add-patient/', views.add_patient, name='add_patient'),
    path('patient/<str:type>/<int:id>/', views.view_patient_dynamic, name='view_patient'),
    path('patients/<int:patient_id>/edit/', views.edit_patient, name='edit_patient'),
    path('patients/<int:patient_id>/delete/', views.delete_patient, name='delete_patient'),
    path('family/edit/<int:id>/', views.edit_family, name='edit_family'),
    path('family/delete/<int:id>/', views.delete_family, name='delete_family'),
    
    path('billing/',views.billing,name='billing'),
    path('appointment/cancel/<int:appointment_id>/', views.cancel_appointment, name='cancel_appointment'),

    path('staff/',views.staff_view,name='staff'),
    path('staff/add/',views.add_staff,name='add_staff'),
    path('staff/edit/<int:member_id>/',views.edit_staff,name='edit_staff'),
    path('staff/delete/<int:member_id>/',views.delete_staff,name='delete_staff'),
    path('staff/reset-password/<int:member_id>/', views.reset_staff_password, name='reset_staff_password'),

]