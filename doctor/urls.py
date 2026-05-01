from django.urls import path
from . import views
from .views import *

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

    path('manage-medicines/', views.ManageMedicineView.as_view(), name='manage_medicine'),
    path('add-medicine/', views.AddMedicineView.as_view(), name='add_medicine'),
    path('delete-medicine/<int:pk>/', views.DeleteMedicineView.as_view(), name='delete_medicine'),
    path('edit-medicine/<int:pk>/', views.EditMedicineView.as_view(), name='edit_medicine'),
    path('billing/',views.billing,name='billing'),
]