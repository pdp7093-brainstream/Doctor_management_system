from django.urls import path
from . import views

app_name = 'doctor'

urlpatterns = [
    path('login/',views.login_view,name='login'),  
    path('logout/',views.logout_view,name='logout'),
    path('dashboard/',views.dashboard,name='dashboard'),
    path('manage-patients/',views.manage_patients,name='manage_patients'),
    path('add-patient/',views.add_patient,name='add_patient'),
    # prescription
    path('view/prescription/',views.prescription,name='prescription'),
    path('billing/',views.billing,name='billing'),
]