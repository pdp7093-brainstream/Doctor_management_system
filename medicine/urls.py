from django.urls import path
from . import views

app_name = 'medicine'

urlpatterns = [
    path('',views.ManageMedicineView.as_view(), name='manage_medicine'),
    path('add/',views.AddMedicineView.as_view(), name='add_medicine'),
    path('delete/<int:pk>/',views.DeleteMedicineView.as_view(), name='delete_medicine'),
    path('edit/<int:pk>/',views.EditMedicineView.as_view(), name='edit_medicine'),
    path('search/', views.MedicineSearchView.as_view(), name='medicine_search'),
]