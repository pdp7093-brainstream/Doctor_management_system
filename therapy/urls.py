from django.urls import path

from . import views

app_name = 'therapy'

urlpatterns = [
    path('', views.TherapyListView.as_view(), name='therapy_list'),
    path('<int:pk>/edit/', views.TherapyEditView.as_view(), name='therapy_edit'),
    path('<int:pk>/delete/', views.TherapyDeleteView.as_view(), name='therapy_delete'),
]