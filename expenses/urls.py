# expenses/urls.py

from django.urls import path
from . import views

app_name = 'expenses'

urlpatterns = [

    # Expense
    path('', views.ExpenseListView.as_view(), name='expense_list'),
    path('add/', views.AddExpenseView.as_view(), name='add_expense'),
    path('pending/', views.pending_expenses, name='pending_expenses'),
    path('expense-detail/<int:pk>/', views.ExpenseDetailView.as_view(), name='expense_detail'),

    # Category
    path('categories/', views.CategoryListView.as_view(), name='category_list'),
    path('categories/add/', views.AddCategoryView.as_view(), name='add_category'),
    path('categories/edit/<int:pk>/',views.EditCategoryView.as_view(),name='edit_category'),
    path('categories/delete/<int:pk>/',views.DeleteCategoryView.as_view(),name='delete_category'),
]