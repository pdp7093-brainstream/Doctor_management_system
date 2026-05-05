from django.urls import path
from . import views
from .views import *

urlpatterns = [
    path('',views.home,name='index'),
    path('about/',views.about,name='about'),
    path('departments/',views.departments,name='departments'),
    path('services/',views.services,name='services'),
    
    path('terms/',views.terms,name='terms'),
    path('contact/',views.contact,name='contact'),
    path('dashboard/',views.dashboard,name='dashboard'),
    path('user-profile/',views.profile,name='profile'), 
    path('change-password/', views.ChangePasswordView.as_view(), name='resetpass'),

    #Authentication urls
    path('login-up/',views.login,name='login'),
    path('sign-up/', SignupView.as_view(), name='signup'),
    path('login/', LoginView.as_view(), name='login'),
    path('logout/',views.logout_view, name='logout'),
    path('profile-setting/',views.profile_settings,name='profile-setting'),

    #Family member urls
    path('add-family-member/', views.add_family_member, name='add_family_member'),
    path('update-family-member/<int:member_id>/', views.update_family_member, name='update_family_member'),
    path('delete-family-member/<int:member_id>/', views.delete_family_member, name='delete_family_member'),
   
]