from django.urls import path
from . import views
from .views import *

app_name = 'medicine'

urlpatterns = [
    path('',ManageMedicineView.as_view(), name='manage_medicine'),
    path('add/',AddMedicineView.as_view(), name='add_medicine'),
    
    path('delete/<str:hid>/',DeleteMedicineView.as_view(), name='delete_medicine'),
    path('edit/<str:hid>/',EditMedicineView.as_view(), name='edit_medicine'),
    path('search/', views.search_medicine, name='search_medicine'),
    path('legacy-search/', MedicineSearchView.as_view(), name='medicine_search'),
    path('low-stock/', LowStockView.as_view(), name='low_stock'),
    path('low-stock-count/', views.low_stock_count, name='low_stock_count'),
    path('low-stock-list/', views.low_stock_list, name='low_stock_list'),

    # Vendor 
    path('vendors/',VendorListView.as_view(),name='vendor_list'),
    path('vendors/add/',AddVendorView.as_view(),name='add_vendor'),
    
    path('vendors/edit/<str:hid>',EditVendorView.as_view(), name="edit_vendor"),
    path('vendors/delete/<str:hid>/',DeleteVendorView.as_view(),name='delete_vendor'),

    # Purchase 
    path('purchases/',PurchaseListView.as_view(),name='purchase_list'),
    path('purchases/add/',AddPurchaseView.as_view(),name='add_purchase'),   
    
    path('purchases/<str:hid>/',PurchaseDetailView.as_view(),name='purchase_detail'),    
    path(
        "purchase/<str:hid>/receive/",
        ReceivePurchaseView.as_view(),
        name="receive_purchase",
    ),
    
    path('purchases/<str:hid>/delete/', DeletePurchaseView.as_view(), name='delete_purchase'),

    # Medicine Importer
    path('import/', ImportMedicineView.as_view(), name='import_medicine'),
]
