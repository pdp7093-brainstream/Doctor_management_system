from django.urls import path
from django.views.generic import RedirectView
from django.contrib.auth import views as auth_views
from . import views
from .views import *
from .forms import PasswordResetEmailForm

urlpatterns = [


    path('',views.home,name='index'),
    path('about/',views.about,name='about'),
    path('treatments/',views.treatments,name='treatments'),
    path('departments/', RedirectView.as_view(pattern_name='treatments', permanent=True), name='departments'),
    path('services/', RedirectView.as_view(pattern_name='treatments', permanent=True), name='services'),

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
    path('activate/<uidb64>/<token>/', views.activate_patient, name='activate_patient'),
    path('remove-profile-picture/', views.remove_profile_picture, name='remove_profile_picture'),
    path('upload-profile-document/', views.upload_profile_document, name='upload_profile_document'),

    # Password reset URLs (Django built-in)
    path('password-reset/', auth_views.PasswordResetView.as_view(
        form_class=PasswordResetEmailForm,
        template_name='authentication/password_reset_form.html',
        email_template_name='authentication/password_reset_email.txt',
        html_email_template_name='authentication/password_reset_email.html',
        subject_template_name='authentication/password_reset_subject.txt',
        success_url='/password-reset/done/',
    ), name='password_reset'),
    path('password-reset/done/', auth_views.PasswordResetDoneView.as_view(
        template_name='authentication/password_reset_done.html',
    ), name='password_reset_done'),
    path('reset/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(
        template_name='authentication/password_reset_confirm.html',
        success_url='/reset/done/',
    ), name='password_reset_confirm'),
    path('reset/done/', auth_views.PasswordResetCompleteView.as_view(
        template_name='authentication/password_reset_complete.html',
    ), name='password_reset_complete'),

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
