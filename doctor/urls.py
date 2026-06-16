from django.urls import path
from django.views.generic import RedirectView
from . import views
from .views import *
from medicine.views import *

app_name = 'doctor'

urlpatterns = [
    path('', RedirectView.as_view(pattern_name='doctor:dashboard', permanent=False), name='doctor_root'),
    path('login/',views.login_view,name='login'),  
    path('logout/',views.logout_view,name='logout'),
    path('profile/', views.my_profile, name='my_profile'),
    path('dashboard/',DashboardView.as_view(),name='dashboard'),
    path('manage-patients/',views.manage_patients,name='manage_patients'),

    path('add-patient/', views.add_patient, name='add_patient'),
    path('patient/<str:type>/<str:hid>/', views.view_patient_dynamic, name='view_patient'),
    path('patients/<str:hid>/edit/', views.edit_patient, name='edit_patient'),
    path('patients/<str:hid>/delete/', views.delete_patient, name='delete_patient'),
    path('family/edit/<str:hid>/', views.edit_family, name='edit_family'),
    path('family/delete/<str:hid>/', views.delete_family, name='delete_family'),
    
    path('billing/',views.billing,name='billing'),
    path('appointment/cancel/<str:hid>/', views.cancel_appointment, name='cancel_appointment'),

    path('staff/',views.staff_view,name='staff'), 
    path('staff/add/',views.add_staff,name='add_staff'),
    path('staff/edit/<int:member_id>/',views.edit_staff,name='edit_staff'),
    path('staff/delete/<int:member_id>/',views.delete_staff,name='delete_staff'),
    path('staff/reset-password/<int:member_id>/', views.reset_staff_password, name='reset_staff_password'),

    path("leaves/", views.manage_leaves, name="manage_leaves"),
    path("leaves/<int:pk>/delete/", views.delete_leave, name="delete_leave"),

    path('settings/', RedirectView.as_view(pattern_name='clinic:settings', permanent=False), name='settings'),
    path('old-data/', views.old_data_upload, name='old_data_upload'),
    path('old-data/delete/<str:hid>/', views.delete_old_document, name='delete_old_document'),

    path('feedback/', views.feedback_list, name='feedback_list'),
    path('feedback/bulk-delete/', views.bulk_delete_feedback, name='bulk_delete_feedback'),
    path('feedback/<int:pk>/delete/', views.delete_feedback, name='delete_feedback'),

]
