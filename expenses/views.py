# expenses/views.py
from django.views import View
from django.shortcuts import render, redirect
from django.contrib import messages
from django.utils import timezone
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404
from .models import Expense, ExpenseCategory
from doctor.mixins import ExpenseAccessMixin
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache

@never_cache
@login_required(login_url='doctor:login')
def pending_expenses(request):

    # Only doctor can access pending approvals
    if request.user.innermember.role != 'doctor':
        return redirect('expenses:expense_list')

    if request.method == 'POST':
        action = request.POST.get('action')
        expense_id = request.POST.get('expense_id')
        
        try:
            expense = Expense.objects.get(id=expense_id, status='pending', is_archived=False)
            if action == 'approve':
                expense.status = 'approved'
                expense.approved_at = timezone.now()
                expense.save()
                
            elif action == 'reject':
                expense.status = 'rejected'
                expense.save()
               
        except Expense.DoesNotExist:
            messages.error(request, 'Expense not found or already processed.')
            
        return redirect('expenses:pending_expenses')

    expenses = Expense.objects.select_related('category','created_by').filter(status='pending', is_archived=False).order_by('-created_at')

    context = {'expenses': expenses}

    return render(request,'expenses/pending_expenses.html',context)

@method_decorator(never_cache, name='dispatch')
class CategoryListView(LoginRequiredMixin, ExpenseAccessMixin, View):

    login_url = 'doctor:login'

    def dispatch(self, request, *args, **kwargs):

        # Only doctor can access categories
        if request.user.innermember.role != 'doctor':

            return redirect('expenses:expense_list')

        return super().dispatch(request, *args, **kwargs)

    def get(self, request):

        categories = ExpenseCategory.objects.all().order_by('name')

        context = {'categories': categories}

        return render(request,'expenses/category_list.html',context)

@method_decorator(never_cache, name='dispatch')
class AddCategoryView(LoginRequiredMixin, ExpenseAccessMixin, View):

    login_url = 'doctor:login'

    def dispatch(self, request, *args, **kwargs):

        # Only doctor can add category
        if request.user.innermember.role != 'doctor':

            return redirect('expenses:expense_list')

        return super().dispatch(request, *args, **kwargs)

    def get(self, request):

        return render(request,'expenses/add_category.html')

    def post(self, request):

        try:

            name = request.POST.get('name')

            ExpenseCategory.objects.create(name=name)

            return redirect('expenses:category_list')

        except Exception as e:

            print("Category Create Error:", e)
            return redirect('expenses:add_category')

@method_decorator(never_cache, name='dispatch')
class AddExpenseView(LoginRequiredMixin, ExpenseAccessMixin, View):

    login_url = 'doctor:login'

    def get(self, request):

        categories = ExpenseCategory.objects.filter(is_active=True).order_by('name')

        context = {'categories': categories}

        return render(request,'expenses/add_expense.html',context)

    def post(self, request):

        try:

            title = request.POST.get('title')
            category_id = request.POST.get('category')
            amount = request.POST.get('amount')
            expense_date = request.POST.get('expense_date')
            notes = request.POST.get('notes')
            attachment = request.FILES.get('attachment')

            category = ExpenseCategory.objects.get(id=category_id)

            member = request.user.innermember

            # Doctor expense → auto approved
            if member.role == 'doctor':

                status = 'approved'

            # Biller expense → pending approval
            else:

                status = 'pending'

            Expense.objects.create(
                title=title,
                category=category,
                amount=amount,
                expense_date=expense_date,
                notes=notes,
                attachment=attachment,
                created_by=request.user,
                status=status
            )

            # Dynamic success message
            # if status == 'approved':

            #     messages.success(request,'Expense added and approved successfully.')

            # else:

            #     messages.success(request,'Expense submitted for approval.')

            return redirect('expenses:expense_list')

        except Exception as e:

            print("Expense Create Error:", e)

            return redirect('expenses:add_expense')

@method_decorator(never_cache, name='dispatch')
class ExpenseListView(LoginRequiredMixin,ExpenseAccessMixin,View):

    login_url = 'doctor:login'

    def get(self, request):

        member = request.user.innermember

        # Doctor → all expenses
        if member.role == 'doctor':

            expenses = Expense.objects.select_related('category','created_by').filter(is_archived=False).order_by('-created_at')

        # Biller → only own expenses
        else:
            expenses = Expense.objects.select_related('category','created_by').filter(created_by=request.user, is_archived=False).order_by('-created_at')

        context = {'expenses': expenses}

        return render(request,'expenses/expense_list.html',context)

@method_decorator(never_cache, name='dispatch')       
class ExpenseDetailView(LoginRequiredMixin, ExpenseAccessMixin, View):

    login_url = 'doctor:login'

    def get(self, request, pk):

        member = request.user.innermember

        # Doctor sab expenses dekh sakta hai
        if member.role == 'doctor':

            expense = get_object_or_404(Expense.objects.select_related('category','created_by'), id=pk, is_archived=False)

        # Biller sirf apna expense
        else:

            expense = get_object_or_404(
                Expense.objects.select_related('category','created_by'), id=pk, created_by=request.user, is_archived=False)

        context = {'expense': expense}

        return render(request,'expenses/expense_detail.html',context)
