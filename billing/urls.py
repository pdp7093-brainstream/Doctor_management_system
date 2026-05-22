from django.urls import path
from . import views

app_name = 'billing'

urlpatterns = [
    path('', views.BillListView.as_view(), name='bill_list'),
    path('visit/<int:visit_id>/', views.BillDetailView.as_view(), name='bill_detail'),
    path('delete/<int:bill_id>/', views.DeleteBillView.as_view(), name='delete_bill'),
    path('visit/<int:visit_id>/print/', views.PrintBillView.as_view(), name='print_bill'),
]