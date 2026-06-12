from django.urls import path
from . import views

app_name = 'billing'

urlpatterns = [
    path('', views.BillListView.as_view(), name='bill_list'),
    path('add/', views.AddBillView.as_view(), name='add_bill'),
    path('visit/<str:hid>/', views.BillDetailView.as_view(), name='bill_detail'),
    path('delete/<str:hid>/', views.DeleteBillView.as_view(), name='delete_bill'),
    path('bulk-delete/', views.BulkDeleteBillView.as_view(), name='bulk_delete_bills'),
    path('visit/<str:hid>/print/', views.PrintBillView.as_view(), name='print_bill'),
]