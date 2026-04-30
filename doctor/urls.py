from django.urls import path
from . import views
from .views import *

app_name = 'doctor'

urlpatterns = [
    path('login/',views.login_view,name='login'),  
    path('logout/',views.logout_view,name='logout'),
    path('dashboard/',DashboardView.as_view(),name='dashboard'),
    path('manage-patients/',views.manage_patients,name='manage_patients'),
    path('add-patient/',views.add_patient,name='add_patient'),
    
    path('billing/',views.billing,name='billing'),
]