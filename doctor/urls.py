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
]