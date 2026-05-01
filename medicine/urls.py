from django.urls import path
from . import views
from .views import *

app_name = 'medicine'

urlpatterns = [
    path('',ManageMedicineView.as_view(), name='manage_medicine'),
    path('add/',AddMedicineView.as_view(), name='add_medicine'),
    path('delete/<int:pk>/',DeleteMedicineView.as_view(), name='delete_medicine'),
    path('edit/<int:pk>/',EditMedicineView.as_view(), name='edit_medicine'),
    path('search/', MedicineSearchView.as_view(), name='medicine_search'),
]