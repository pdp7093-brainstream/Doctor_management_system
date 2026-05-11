# prescription/urls.py

from django.urls import path
from . import views

urlpatterns = [
    path('', views.upload_prescription, name='upload_prescription'),
]