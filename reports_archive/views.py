from django.views import View
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.shortcuts import redirect
import csv
from django.http import HttpResponse
from appointment.models import Appointment
from billing.models import Bill
from expenses.models import Expense
from django.utils import timezone
from datetime import timedelta
from django.core.paginator import Paginator
from django.db.models import Q
from django.utils.dateparse import parse_date


def appointment_patient_name(appointment):
    if appointment.family_member:
        return appointment.family_member.name

    return appointment.patient.user.get_full_name() or appointment.patient.user.username


def create_workbook(request):
    try:
        from openpyxl import Workbook
    except ImportError:
        messages.error(request, 'Excel export requires openpyxl. Please install it or export as CSV.')
        return None

    return Workbook()


class DoctorRequiredMixin(LoginRequiredMixin):
    login_url = 'doctor:login'

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect(self.login_url)

        try:
            role = request.user.innermember.role
        except Exception:
            messages.error(request, 'Access denied.')
            return redirect('doctor:login')

        if role != 'doctor':
            messages.error(request, 'Access denied.')
            return redirect('doctor:dashboard')

        return super().dispatch(request, *args, **kwargs)

class ExportDataView(DoctorRequiredMixin, View):

    def get(self, request):

        context = {}

        return render(request,'reports_archive/export_data.html',context)

    def post(self, request):
        data_type = request.POST.get('data_type')
        export_format = request.POST.get('export_format')

        from_date = request.POST.get('from_date')
        to_date = request.POST.get('to_date')

        if not from_date or not to_date:
            messages.error(request, 'Please select both From Date and To Date to export data.')
            return redirect('reports_archive:export_data')

        # Only appointments for now
        if data_type == 'appointments':
            appointments = Appointment.objects.filter(
                appointment_date__range = [from_date, to_date],
                is_archived=False,
            )

            if export_format == 'csv':

                response = HttpResponse(content_type='text/csv')

                response['Content-Disposition'] = ('attachment; filename = "appointments.csv"')

                writer = csv.writer(response)

                # Header
                writer.writerow(['Patient Name','Date','Slot','Status'])

                # Data
                for appointment in appointments:

                    writer.writerow([
                        f"{appointment.patient.user.first_name} {appointment.patient.user.last_name}",
                        appointment.appointment_date,
                        appointment.time_slot, appointment.status,
                    ])

                return response

            elif export_format == 'xlsx':
                workbook = create_workbook(request)
                if workbook is None:
                    return redirect('reports_archive:export_data')
                sheet = workbook.active
                sheet.title = 'Appointments'

                # Headers
                sheet.append(['Patient Name', 'Date','Slot','Status'])

                # Data
                for appointment in appointments:
                    sheet.append([
                        f"{appointment.patient.user.first_name} {appointment.patient.user.last_name}",
                        str(appointment.appointment_date),
                        str(appointment.time_slot),
                        appointment.status,
                    ])

                response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

                response['Content-Disposition'] = ('attachment; filename="appointments.xlsx"')

                workbook.save(response)

                return response

            messages.error(request, 'invalid export type.')
            return redirect('reports_archive:export_data')

        elif data_type == 'bills':

            bills = Bill.objects.filter(
                created_at__date__range=[from_date, to_date],
                is_archived=False,
            )

            if export_format == 'csv':
                response = HttpResponse(content_type='text/csv')

                response['Content-Disposition'] = (
                    'attachment; filename="bills.csv"'
                )

                writer = csv.writer(response)

                writer.writerow([
                    'Bill Number','Patient','Date','Total Amount','Status',
                ])

                for bill in bills:

                    writer.writerow([
                        bill.bill_number,
                        f"{bill.visit.patient.user.first_name} {bill.visit.patient.user.last_name}",
                        bill.bill_date,
                        bill.total,
                        bill.payment_status,
                    ])

                return response

            elif export_format == 'xlsx':
                workbook = create_workbook(request)
                if workbook is None:
                    return redirect('reports_archive:export_data')
                sheet = workbook.active
                sheet.title = 'Bills'

                # Headers
                sheet.append(['Patient Name','Date','Bill Number','Total Amount','Status',])

                for bill in bills:
                    sheet.append([
                        f"{bill.visit.patient.user.first_name} {bill.visit.patient.user.last_name}",
                        str(bill.bill_date),
                        bill.bill_number,
                        bill.total,
                        bill.payment_status,
                    ])

                response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

                response['Content-Disposition'] = ('attachment; filename="bills.xlsx"')

                workbook.save(response)

                return response

        elif data_type == 'expenses':

            expenses = Expense.objects.filter(
                expense_date__range=[from_date, to_date],
                is_archived=False,
            )


            if export_format == 'csv':
                response = HttpResponse(content_type='text/csv')

                response['Content-Disposition'] = (
                    'attachment; filename="expenses.csv"'
                )

                writer = csv.writer(response)

                writer.writerow([
                    'Title','Category','Amount','Expense Date','Status','Created By',
                ])

                for expense in expenses:

                    writer.writerow([
                        expense.title,
                        expense.category.name,
                        expense.amount,
                        expense.expense_date,
                        expense.status,
                        expense.created_by.get_full_name() or expense.created_by.username,
                    ])

                return response

            elif export_format == 'xlsx':
                workbook = create_workbook(request)
                if workbook is None:
                    return redirect('reports_archive:export_data')
                sheet = workbook.active
                sheet.title = 'Expenses'

                # Headers
                sheet.append(['Title','Category','Amount','Expense Date','Status','Created By',])

                for expense in expenses:
                    sheet.append([
                        expense.title,
                        expense.category.name,
                        expense.amount,
                        str(expense.expense_date),
                        expense.status,
                        expense.created_by.get_full_name() or expense.created_by.username,
                    ])

                response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

                response['Content-Disposition'] = ('attachment; filename="expenses.xlsx"')

                workbook.save(response)

                return response

        else:
            messages.error(request, 'Invalid export type.')
            return redirect('reports_archive:export_data')


class ArchiveRecordsView(DoctorRequiredMixin, View):

    def get(self, request):

        context = {
            'active_appointments_count': Appointment.objects.filter(is_archived=False).count(),
            'archived_appointments_count': Appointment.objects.filter(is_archived=True).count(),
            'active_bills_count': Bill.objects.filter(is_archived=False).count(),
            'archived_bills_count': Bill.objects.filter(is_archived=True).count(),
            'active_expenses_count': Expense.objects.filter(is_archived=False).count(),
            'archived_expenses_count': Expense.objects.filter(is_archived=True).count(),
        }

        return render(request,'reports_archive/archive_records.html', context)

    def post(self, request):
        data_type = request.POST.get('data_type')
        archive_age = request.POST.get('archive_age')
        archive_type = request.POST.get('archiveType')

        today = timezone.now().date()

        cutoff_map = {
            '6_months': today - timedelta(days=180),
            '1_year': today - timedelta(days=365),
            '2_years': today - timedelta(days=730),
        }
        cutoff_date = cutoff_map.get(archive_age)

        if not cutoff_date:
            messages.error(request,'Invalid archive duration.')

            return redirect('reports_archive:archive_records')

        archive_map = {
            'appointments': (
                Appointment.objects.filter(appointment_date__lt=cutoff_date, is_archived=False),
                'appointments',
            ),
            'bills': (
                Bill.objects.filter(bill_date__lt=cutoff_date, is_archived=False),
                'bills',
            ),
            'expenses': (
                Expense.objects.filter(expense_date__lt=cutoff_date, is_archived=False),
                'expenses',
            ),
        }

        archive_config = archive_map.get(data_type)

        if not archive_config:
            messages.error(request,'Invalid archive type.')
            return redirect('reports_archive:archive_records')

        queryset, label = archive_config

        # If export_archive is selected, generate CSV before archiving
        if archive_type == 'export_archive':
            response = HttpResponse(content_type='text/csv')
            response['Content-Disposition'] = f'attachment; filename="{label}_backup.csv"'
            writer = csv.writer(response)

            if data_type == 'appointments':
                # Headers for appointments
                writer.writerow(['Patient Name', 'Date', 'Slot', 'Status'])
                # Data
                for appointment in queryset:
                    writer.writerow([
                        appointment_patient_name(appointment),
                        appointment.appointment_date,
                        appointment.time_slot,
                        appointment.status,
                    ])

            elif data_type == 'bills':
                # Headers for bills
                writer.writerow(['Bill Number', 'Patient Name', 'Date', 'Total Amount', 'Status'])
                # Data
                for bill in queryset:
                    writer.writerow([
                        bill.bill_number,
                        f"{bill.visit.patient.user.first_name} {bill.visit.patient.user.last_name}",
                        bill.bill_date,
                        bill.total,
                        bill.payment_status,
                    ])

            elif data_type == 'expenses':
                # Headers for expenses
                writer.writerow(['Title', 'Category', 'Amount', 'Date', 'Status', 'Created By'])
                # Data
                for expense in queryset:
                    writer.writerow([
                        expense.title,
                        expense.category.name,
                        expense.amount,
                        expense.expense_date,
                        expense.status,
                        expense.created_by.get_full_name() or expense.created_by.username,
                    ])

            # Now archive the records
            archived_count = queryset.update(is_archived=True, archived_at=timezone.now())
            
            return response

        # If archive_only is selected, just archive without exporting
        elif archive_type == 'archive_only':
            archived_count = queryset.update(is_archived=True, archived_at=timezone.now())
            messages.success(
                request,
                f'{archived_count} {label} archived successfully.'
            )
            return redirect('reports_archive:archive_records')

        else:
            messages.error(request, 'Invalid archive type.')
            return redirect('reports_archive:archive_records')


class ArchivedAppointmentsView(DoctorRequiredMixin, View):
    def get(self, request):
        search = request.GET.get('search', '').strip()
        appointment_date = request.GET.get('appointment_date', '').strip()
        status = request.GET.get('status', 'all').strip()

        appointments = Appointment.objects.select_related(
            'patient__user',
            'family_member',
            'doctor__user',
            'booked_by',
        ).filter(is_archived=True)

        if search:
            appointments = appointments.filter(
                Q(patient__user__first_name__icontains=search) |
                Q(patient__user__last_name__icontains=search) |
                Q(patient__phone__icontains=search) |
                Q(family_member__name__icontains=search) |
                Q(family_member__phone__icontains=search)
            )

        if appointment_date:
            parsed_date = parse_date(appointment_date)
            appointments = appointments.filter(appointment_date=parsed_date) if parsed_date else appointments.none()

        if status and status != 'all':
            appointments = appointments.filter(status=status)

        appointments = appointments.order_by('-archived_at', '-appointment_date', '-time_slot')
        paginator = Paginator(appointments, 10)
        page_obj = paginator.get_page(request.GET.get('page'))

        context = {
            'appointments': page_obj,
            'page_obj': page_obj,
            'search': search,
            'appointment_date': appointment_date,
            'status': status,
            'status_choices': Appointment.status_choices,
            'active_appointments_count': Appointment.objects.filter(is_archived=False).count(),
            'archived_appointments_count': Appointment.objects.filter(is_archived=True).count(),
        }

        return render(request, 'reports_archive/archived_appointments.html', context)


class RestoreAppointmentView(DoctorRequiredMixin, View):
    def post(self, request, appointment_id):
        appointment = get_object_or_404(Appointment, id=appointment_id, is_archived=True)
        appointment.is_archived = False
        appointment.archived_at = None
        appointment.save(update_fields=['is_archived', 'archived_at'])

        messages.success(request, 'Appointment restored successfully.')
        return redirect('reports_archive:archived_appointments')


class ArchivedBillsView(DoctorRequiredMixin, View):
    def get(self, request):
        bills = Bill.objects.select_related(
            'visit__patient__user'
        ).filter(is_archived=True).order_by('-archived_at', '-created_at')

        page_obj = Paginator(bills, 10).get_page(request.GET.get('page'))

        return render(request, 'reports_archive/archived_bills.html', {
            'bills': page_obj,
            'page_obj': page_obj,
            'active_bills_count': Bill.objects.filter(is_archived=False).count(),
            'archived_bills_count': Bill.objects.filter(is_archived=True).count(),
        })


class RestoreBillView(DoctorRequiredMixin, View):
    def post(self, request, bill_id):
        bill = get_object_or_404(Bill, id=bill_id, is_archived=True)
        bill.is_archived = False
        bill.archived_at = None
        bill.save(update_fields=['is_archived', 'archived_at'])

        messages.success(request, f'Bill {bill.bill_number} restored successfully.')
        return redirect('reports_archive:archived_bills')


class ArchivedExpensesView(DoctorRequiredMixin, View):
    def get(self, request):
        expenses = Expense.objects.select_related(
            'category',
            'created_by',
        ).filter(is_archived=True).order_by('-archived_at', '-created_at')

        page_obj = Paginator(expenses, 10).get_page(request.GET.get('page'))

        return render(request, 'reports_archive/archived_expenses.html', {
            'expenses': page_obj,
            'page_obj': page_obj,
            'active_expenses_count': Expense.objects.filter(is_archived=False).count(),
            'archived_expenses_count': Expense.objects.filter(is_archived=True).count(),
        })


class RestoreExpenseView(DoctorRequiredMixin, View):
    def post(self, request, expense_id):
        expense = get_object_or_404(Expense, id=expense_id, is_archived=True)
        expense.is_archived = False
        expense.archived_at = None
        expense.save(update_fields=['is_archived', 'archived_at'])

        messages.success(request, 'Expense restored successfully.')
        return redirect('reports_archive:archived_expenses')
