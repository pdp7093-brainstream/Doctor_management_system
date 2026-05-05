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
    path('patients/<int:patient_id>/', views.view_patient, name='view_patient'),
    path('patients/<int:patient_id>/edit/', views.edit_patient, name='edit_patient'),
    path('patients/<int:patient_id>/delete/', views.delete_patient, name='delete_patient'),
    
    path('billing/',views.billing,name='billing'),

    path('staff/',views.staff_view,name='staff'),
    path('staff/add/',views.add_staff,name='add_staff'),
    path('staff/edit/<int:member_id>/',views.edit_staff,name='edit_staff'),
    path('staff/delete/<int:member_id>/',views.delete_staff,name='delete_staff'),
    path('staff/reset-password/<int:member_id>/', views.reset_staff_password, name='reset_staff_password'),

]