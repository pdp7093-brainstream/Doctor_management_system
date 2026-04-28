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

    #Authentication
    path('login-up/',views.login,name='login'),
    path('sign-up/', SignupView.as_view(), name='signup'),
    path('login/', LoginView.as_view(), name='login'),
    path('logout/',views.logout_view, name='logout'),
    path('profile-setting/',views.profile_settings,name='profile-setting'),
   
]