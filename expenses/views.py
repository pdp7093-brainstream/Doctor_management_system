# expenses/views.py
import logging

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
from django.db import IntegrityError

logger = logging.getLogger(__name__)

@never_cache
@login_required(login_url='doctor:login')
def pending_expenses(request):

    # Only doctor can access pending approvals
    if request.user.innermember.role != 'doctor':
        return redirect('expenses:expense_list')

    if request.method == 'POST':
        action = request.POST.get('action')
        expense_id = request.POST.get('expense_id')
        # decode possible hashid
        from doctor import hashid as _hashid
        try:
            try:
                eid = _hashid.decode_hash(expense_id)
            except Exception:
                eid = int(expense_id)

            expense = Expense.objects.get(id=eid, status='pending', is_archived=False)
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
        # The add-category form is available on the category list page.
        # Redirect there to avoid TemplateDoesNotExist when visiting /expenses/categories/add/
        return redirect('expenses:category_list')

    def post(self, request):

        name = request.POST.get('name')
        is_active = request.POST.get('is_active') == 'on'
        try:
            ExpenseCategory.objects.create(name=name, is_active=is_active)
            messages.success(request, 'Category created successfully.')
            return redirect('expenses:category_list')
        except IntegrityError:
            # Duplicate category name
            messages.error(request, 'A category with this name already exists.')
            return redirect('expenses:category_list')
        except Exception as exc:
            logger.exception("Category Create Error for name=%r: %s", name, exc)
            messages.error(request, 'Failed to create category.')
            return redirect('expenses:category_list')

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

            return redirect('expenses:expense_list')

        except Exception as exc:
            logger.exception("Expense Create Error by user=%s: %s", request.user.username, exc)
            messages.error(request, 'Failed to create expense. Please check your inputs.')
            return redirect('expenses:add_expense')


@method_decorator(never_cache, name='dispatch')
class EditCategoryView(LoginRequiredMixin, ExpenseAccessMixin,View):
    login_url = 'doctor:login'

    def dispatch(self,request, *args, **kwargs):
        if request.user.innermember.role != 'doctor':
            return redirect('expenses:expense_list')
        
        return super().dispatch(request,*args,**kwargs)

    def get(self,request,hid):
        pk = hid
        category = get_object_or_404(ExpenseCategory, id=pk)

        context = {'category':category}

        return render(request, 'expenses/edit_category.html',context)

    def post(self,request, pk):
        pk = pk
        category = get_object_or_404(ExpenseCategory, id=pk)

        category.name = request.POST.get('name')
        category.is_active = request.POST.get('is_active') == 'on'

        category.save()

        return redirect('expenses:category_list')


@method_decorator(never_cache, name='dispatch')
class DeleteCategoryView(LoginRequiredMixin, ExpenseAccessMixin, View):
    login_url = 'doctor:login'

    def dispatch(self, request, *args, **kwargs):
        if request.user.innermember.role != 'doctor':
            return redirect('expenses:expense_list')
        
        return super().dispatch(request, *args, **kwargs)

    def post(self, request,pk):
        pk = pk
        category = get_object_or_404(ExpenseCategory, id=pk)
        
        # Prevent deletion if expenses are linked to this category
        if category.expenses.exists():
            messages.error(request, 'Cannot delete this category because it contains existing expenses. Please delete or reassign the expenses first.')
            return redirect('expenses:category_list')

        try:
            category.delete()
            messages.success(request, 'Category deleted successfully.')
        except Exception as exc:
            logger.exception("Category Delete Error for id=%s: %s", pk if 'pk' in dir() else '?', exc)
            messages.error(request, 'Failed to delete category. It might be in use.')
        
        return redirect('expenses:category_list')


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

    def get(self, request, hid):
        pk = hid
        # accept hashid or numeric id
        from doctor import hashid as _hashid
        try:
            if not str(pk).isdigit():
                pk = _hashid.decode_hash(pk)
            else:
                pk = int(pk)
        except Exception:
            return redirect('expenses:expense_list')

        member = request.user.innermember

        # Doctor can see all expenses
        if member.role == 'doctor':

            expense = get_object_or_404(Expense.objects.select_related('category','created_by'), id=pk, is_archived=False)

        # Biller can only see their own expenses
        else:

            expense = get_object_or_404(
                Expense.objects.select_related('category','created_by'), id=pk, created_by=request.user, is_archived=False)

        context = {'expense': expense}

        return render(request,'expenses/expense_detail.html',context)


@method_decorator(never_cache, name='dispatch')
class EditExpenseView(LoginRequiredMixin, ExpenseAccessMixin, View):
    login_url = 'doctor:login'

    def get(self, request, hid):
        pk = hid
        # accept hashid or numeric id
        from doctor import hashid as _hashid
        try:
            if not str(pk).isdigit():
                pk = _hashid.decode_hash(pk)
            else:
                pk = int(pk)
        except Exception:
            return redirect('expenses:expense_list')

        member = request.user.innermember
        
        if member.role == 'doctor':
            expense = get_object_or_404(Expense, id=pk, is_archived=False)
        else:
            # Biller can only edit their own pending expenses
            expense = get_object_or_404(Expense, id=pk, created_by=request.user, is_archived=False)
            if expense.status != 'pending':
                messages.error(request, 'You can only edit pending expenses. Approved or rejected expenses cannot be modified.')
                return redirect('expenses:expense_detail', hid=pk)

        categories = ExpenseCategory.objects.filter(is_active=True).order_by('name')
        # If current expense category is inactive, we should still show it in the list
        if expense.category not in categories:
            categories = list(categories) + [expense.category]

        context = {
            'expense': expense,
            'categories': categories
        }
        return render(request, 'expenses/edit_expense.html', context)

    def post(self, request, hid):
        pk = hid
        # accept hashid or numeric id
        from doctor import hashid as _hashid
        try:
            if not str(pk).isdigit():
                pk = _hashid.decode_hash(pk)
            else:
                pk = int(pk)
        except Exception:
            return redirect('expenses:expense_list')

        member = request.user.innermember
        
        if member.role == 'doctor':
            expense = get_object_or_404(Expense, id=pk, is_archived=False)
        else:
            expense = get_object_or_404(Expense, id=pk, created_by=request.user, is_archived=False)
            if expense.status != 'pending':
                messages.error(request, 'You can only edit pending expenses. Approved or rejected expenses cannot be modified.')
                return redirect('expenses:expense_detail', hid=pk)

        try:
            expense.title = request.POST.get('title')
            category_id = request.POST.get('category')
            expense.category = ExpenseCategory.objects.get(id=category_id)
            expense.amount = request.POST.get('amount')
            expense.expense_date = request.POST.get('expense_date')
            expense.notes = request.POST.get('notes')
            
            attachment = request.FILES.get('attachment')
            if attachment:
                expense.attachment = attachment

            expense.save()
            messages.success(request, 'Expense updated successfully.')
            return redirect('expenses:expense_detail', hid=pk)

        except Exception as exc:
            logger.exception("Expense Edit Error for id=%s by user=%s: %s", pk, request.user.username, exc)
            messages.error(request, 'Failed to update expense. Please check your inputs.')
            return redirect('expenses:edit_expense', hid=pk)


@method_decorator(never_cache, name='dispatch')
class DeleteExpenseView(LoginRequiredMixin, ExpenseAccessMixin, View):
    login_url = 'doctor:login'

    def post(self, request, hid):
        pk = hid
        # accept hashid or numeric id
        from doctor import hashid as _hashid
        try:
            if not str(pk).isdigit():
                pk = _hashid.decode_hash(pk)
            else:
                pk = int(pk)
        except Exception:
            return redirect('expenses:expense_list')

        member = request.user.innermember
        
        if member.role == 'doctor':
            expense = get_object_or_404(Expense, id=pk, is_archived=False)
        else:
            # Biller can only delete their own pending expenses
            expense = get_object_or_404(Expense, id=pk, created_by=request.user, is_archived=False)
            if expense.status != 'pending':
                messages.error(request, 'You can only delete pending expenses.')
                return redirect('expenses:expense_detail', hid=pk)

        try:
            expense.delete()
            messages.success(request, 'Expense deleted successfully.')
        except Exception as exc:
            logger.exception("Expense Delete Error for id=%s: %s", pk, exc)
            messages.error(request, 'Failed to delete expense.')
            
        return redirect('expenses:expense_list')

