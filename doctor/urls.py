from django.urls import path
from . import views

app_name = 'doctor'

urlpatterns = [
    path('login/',views.login_view,name='login'),  
    path('logout/',views.logout_view,name='logout'),
    path('dashboard/',views.dashboard,name='dashboard'),
    path('manage-patients/',views.manage_patients,name='manage_patients'),
    path('add-patient/',views.add_patient,name='add_patient'),
    path('manage-medicines/', views.ManageMedicineView.as_view(), name='manage_medicine'),
    path('add-medicine/', views.AddMedicineView.as_view(), name='add_medicine'),
    path('delete-medicine/<int:pk>/', views.DeleteMedicineView.as_view(), name='delete_medicine'),
    path('edit-medicine/<int:pk>/', views.EditMedicineView.as_view(), name='edit_medicine'),
    path('billing/',views.billing,name='billing'),
]