from django.urls import path
from . import views
from .views import *

urlpatterns = [


    path('',views.home,name='index'),
    path('about/',views.about,name='about'),
    path('departments/',views.departments,name='departments'),
    path('services/',views.services,name='services'),


    path('terms/',views.terms,name='terms'),
    path('feedback/',views.feedback,name='feedback'),
    path('dashboard/',views.dashboard,name='dashboard'),
    path('user-profile/',views.profile,name='profile'), 
    path('change-password/', views.ChangePasswordView.as_view(), name='resetpass'),


    #Authentication urls        
    path('sign-up/', SignupView.as_view(), name='signup'),
    path('login/', LoginView.as_view(), name='login'),
    path('logout/',views.logout_view, name='logout'),
    path('profile-setting/',views.profile_settings,name='profile-setting'),
    path('upload-profile-document/', views.upload_profile_document, name='upload_profile_document'),


    # document delete endpoints
    path('delete-lab-document/<str:hid>/', views.delete_lab_document, name='delete_lab_document'),
    path('delete-profile-document/<str:hid>/', views.delete_profile_document, name='delete_profile_document'),


    #Family member urls
    path('add-family-member/', views.add_family_member, name='add_family_member'),
    path('update-family-member/<str:hid>/', views.update_family_member, name='update_family_member'),
    path('delete-family-member/<str:hid>/', views.delete_family_member, name='delete_family_member'),


    # Changing phone number
    path('change-phone/', views.change_phone, name='change_phone'),


]
