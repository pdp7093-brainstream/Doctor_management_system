from django.urls import path

from . import views

app_name = 'therapy'

urlpatterns = [
    path('', views.TherapyListView.as_view(), name='therapy_list'),
    path('sessions/', views.TherapySessionsView.as_view(), name='therapy_sessions'),
    path('sessions/<int:pk>/', views.TherapySessionDetailView.as_view(), name='therapy_session_detail'),
    path('sessions/<int:session_pk>/undo/', views.UndoTherapySessionView.as_view(), name='undo_session'),
    path('sessions/<int:pk>/record/', views.MarkTherapySessionDoneView.as_view(), name='mark_session_done'),
    path('sessions/<int:pk>/delete-session/', views.DeleteTherapySessionView.as_view(), name='delete_session'),
    path('sessions/<int:pk>/remove/', views.RemoveTherapyView.as_view(), name='remove_therapy'),
    path('sessions/<int:pk>/complete-early/', views.CompleteEarlyView.as_view(), name='complete_early'),
    path('sessions/<int:pk>/bill-sessions/', views.BillTherapySessionsView.as_view(), name='bill_therapy_sessions'),
    path('sessions/<int:pk>/bill-package/', views.BillTherapyPackageView.as_view(), name='bill_therapy_package'),
    path('<int:pk>/edit/', views.TherapyEditView.as_view(), name='therapy_edit'),
    path('<int:pk>/delete/', views.TherapyDeleteView.as_view(), name='therapy_delete'),
]
