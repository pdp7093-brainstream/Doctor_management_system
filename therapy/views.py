from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.db import transaction
from django.db.models import Count, Max, Q
from django.http import HttpResponseNotAllowed, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.views import View

from billing.models import Bill
from doctor.hashid import encode_id
from doctor.mixins import BillingAccessMixin
from .models import (
    BILLING_TYPE_CHOICES,
    BILLING_TYPE_PACKAGE,
    BILLING_TYPE_PER_SESSION,
    PrescriptionTherapy,
    Therapy,
    TherapyBillItem,
    TherapySession,
)


def create_direct_therapy_bill(visit, payment_method, line_items, notes=''):
    original_bill = Bill.objects.filter(visit=visit, is_addon=False, is_archived=False).first()
    is_addon = bool(original_bill)
    parent_bill = original_bill if is_addon else None

    subtotal = sum((item['amount'] for item in line_items), Decimal('0'))
    valid_payment_methods = dict(Bill.PAYMENT_METHOD)
    method = payment_method if payment_method in valid_payment_methods else 'cash'

    bill = Bill.objects.create(
        visit=visit,
        is_addon=is_addon,
        parent_bill=parent_bill,
        consultation_fee=Decimal('0'),
        subtotal=subtotal,
        gst_percent=Decimal('0'),
        gst_amount=Decimal('0'),
        discount=Decimal('0'),
        total=subtotal,
        payment_method=method,
        payment_status='paid',
        notes=notes or '',
    )

    for item in line_items:
        TherapyBillItem.objects.create(
            bill=bill,
            prescription_therapy=item['prescribed'],
            therapy_name=item['name'],
            billing_type=item['billing_type'],
            sessions=item['sessions'],
            unit_price=item['unit_price'],
            amount=item['amount'],
        )

    return bill


def parse_non_negative_int(value, fallback=0):
    try:
        parsed = int(value)
        return parsed if parsed >= 0 else fallback
    except (TypeError, ValueError):
        return fallback


def therapy_form_values(request):
    name = request.POST.get('name', '').strip()
    try:
        session_price = Decimal(request.POST.get('session_price', request.POST.get('price_per_session', '0')).strip() or '0')
    except (InvalidOperation, AttributeError):
        session_price = None
    package_price_raw = request.POST.get('package_price', '').strip()
    try:
        package_price = Decimal(package_price_raw) if package_price_raw else None
    except (InvalidOperation, AttributeError):
        package_price = False
    default_billing_type = request.POST.get('default_billing_type', 'per_session')
    if default_billing_type not in dict(BILLING_TYPE_CHOICES):
        default_billing_type = 'per_session'
    return {
        'name': name,
        'description': request.POST.get('description', '').strip(),
        'duration_minutes': parse_non_negative_int(request.POST.get('duration_minutes'), 45),
        'price_per_session': session_price or Decimal('0'),
        'session_price': session_price,
        'package_price': package_price,
        'default_billing_type': default_billing_type,
        'default_sessions': max(parse_non_negative_int(request.POST.get('default_sessions'), 1), 1),
        'is_active': request.POST.get('is_active') == 'on',
        'sort_order': parse_non_negative_int(request.POST.get('sort_order')),
    }


def therapy_sessions_redirect(request, query=''):
    url = redirect('doctor:therapy:therapy_sessions').url
    return f'{url}?{query}' if query else url


class TherapyListView(LoginRequiredMixin, View):
    login_url = 'doctor:login'

    def get(self, request):
        therapies = Therapy.objects.annotate(
            prescribed_count=Count('prescriptiontherapy__prescription', distinct=True)
        ).order_by('sort_order', 'name')
        paginator = Paginator(therapies, 20)
        page_number = request.GET.get('page')
        try:
            page_obj = paginator.page(page_number)
        except (PageNotAnInteger, EmptyPage):
            page_obj = paginator.page(paginator.num_pages or 1)
        return render(request, 'therapy/therapy_list.html', {'therapies': page_obj, 'page_obj': page_obj})

    def post(self, request):
        values = therapy_form_values(request)
        if not values['name']:
            messages.error(request, 'Therapy name is required.')
        elif Therapy.objects.filter(name__iexact=values['name']).exists():
            messages.error(request, f"Therapy '{values['name']}' already exists.")
        elif values['session_price'] is None or values['package_price'] is False:
            messages.error(request, 'Enter valid therapy prices.')
        else:
            Therapy.objects.create(**values)
            messages.success(request, f"Therapy '{values['name']}' added successfully.")
        return redirect('doctor:therapy:therapy_list')


class TherapyEditView(LoginRequiredMixin, View):
    login_url = 'doctor:login'

    def get(self, request, pk):
        therapy = get_object_or_404(Therapy, pk=pk)
        return render(request, 'therapy/therapy_edit.html', {'therapy': therapy})

    def post(self, request, pk):
        therapy = get_object_or_404(Therapy, pk=pk)
        values = therapy_form_values(request)
        if not values['name']:
            messages.error(request, 'Therapy name is required.')
        elif Therapy.objects.filter(name__iexact=values['name']).exclude(pk=pk).exists():
            messages.error(request, f"Therapy '{values['name']}' already exists.")
        elif values['session_price'] is None or values['package_price'] is False:
            messages.error(request, 'Enter valid therapy prices.')
        else:
            for field, value in values.items():
                setattr(therapy, field, value)
            therapy.save()
            messages.success(request, f"Therapy '{therapy.name}' updated successfully.")
        return redirect('doctor:therapy:therapy_edit', pk=pk)


class TherapyDeleteView(LoginRequiredMixin, View):
    login_url = 'doctor:login'

    def get(self, request, pk):
        return HttpResponseNotAllowed(['POST'])

    def post(self, request, pk):
        therapy = get_object_or_404(Therapy, pk=pk)
        used_count = therapy.prescriptiontherapy_set.values('prescription_id').distinct().count()
        if used_count:
            messages.error(request, f'Used in {used_count} prescriptions. Deactivate it instead.')
        else:
            name = therapy.name
            therapy.delete()
            messages.success(request, f"Therapy '{name}' deleted successfully.")
        return redirect('doctor:therapy:therapy_list')


class TherapySessionsView(LoginRequiredMixin, BillingAccessMixin, View):
    login_url = 'doctor:login'

    def get(self, request):
        status_param = request.GET.get('status', 'active')
        if not status_param:
            selected_status = 'active'
        elif status_param in {'active', 'completed', 'all'}:
            selected_status = status_param
        else:
            selected_status = 'active'

        search = request.GET.get('search', '').strip()
        selected_therapy = request.GET.get('therapy', '').strip()
        selected_billing_type = request.GET.get('billing_type', '').strip()

        therapies = PrescriptionTherapy.objects.select_related(
            'therapy',
            'package_billed__visit',
            'prescription__visit__patient__user',
            'prescription__visit__appointment__family_member',
        ).prefetch_related('session_records__bill', 'therapy_bill_items__bill__visit').annotate(
            last_session_date=Max('session_records__date')
        )

        if selected_status != 'all':
            therapies = therapies.filter(status=selected_status)

        if search:
            therapies = therapies.filter(
                Q(prescription__visit__patient__user__first_name__icontains=search)
                | Q(prescription__visit__patient__user__last_name__icontains=search)
                | Q(prescription__visit__patient__phone__icontains=search)
                | Q(prescription__visit__appointment__family_member__name__icontains=search)
                | Q(prescription__visit__appointment__family_member__phone__icontains=search)
            )

        if selected_therapy:
            if selected_therapy.isdigit():
                therapies = therapies.filter(therapy_id=int(selected_therapy))
            else:
                therapies = therapies.filter(therapy__name__iexact=selected_therapy)

        if selected_billing_type:
            therapies = therapies.filter(billing_type=selected_billing_type)

        therapies = list(therapies.order_by('-created_at').distinct())

        for item in therapies:
            records = item.session_records.all()
            unbilled = [
                session for session in records
                if session.status == TherapySession.STATUS_DONE and session.bill_id is None
            ]
            item.unbilled_count = len(unbilled)
            item.unbilled_total = (item.session_price or Decimal('0')) * item.unbilled_count
            item.unbilled_session_numbers = [s.session_no for s in unbilled]
            item.next_session_no = max(
                (session.session_no for session in records), default=0
            ) + 1
            if not item.package_billed_id:
                pkg_item = next(
                    (bi for bi in item.therapy_bill_items.all() if bi.billing_type == BILLING_TYPE_PACKAGE),
                    None
                )
                if pkg_item and pkg_item.bill:
                    item.package_billed = pkg_item.bill

            has_billed_sessions = any(s.bill_id is not None for s in records)
            has_billed_package = bool(item.package_billed_id or getattr(item, 'package_billed', None))
            has_billed_items = any(bi.bill_id is not None for bi in item.therapy_bill_items.all())
            item.can_delete_therapy = not has_billed_sessions and not has_billed_package and not has_billed_items
            done_count = sum(1 for s in records if s.status == TherapySession.STATUS_DONE)
            item.can_complete_early = item.status == 'active' and done_count >= 1

        all_therapies = Therapy.objects.all().order_by('sort_order', 'name')

        paginator = Paginator(therapies, 20)
        page_number = request.GET.get('page')
        try:
            page_obj = paginator.page(page_number)
        except (PageNotAnInteger, EmptyPage):
            page_obj = paginator.page(paginator.num_pages or 1)

        return render(request, 'therapy/session_list.html', {
            'therapies': page_obj,
            'page_obj': page_obj,
            'selected_status': selected_status,
            'search': search,
            'selected_therapy': selected_therapy,
            'selected_billing_type': selected_billing_type,
            'all_therapies': all_therapies,
            'today': timezone.localdate(),
        })


class MarkTherapySessionDoneView(LoginRequiredMixin, BillingAccessMixin, View):
    login_url = 'doctor:login'

    def post(self, request, pk):
        is_ajax = (
            request.headers.get('x-requested-with') == 'XMLHttpRequest'
            or 'application/json' in request.headers.get('accept', '')
        )
        return_to = request.POST.get('return_to', '')
        if not return_to.startswith('/') or return_to.startswith('//'):
            return_to = redirect('doctor:therapy:therapy_sessions').url
        return_query = request.POST.get('return_query', '').strip('?')
        if return_query:
            return_to = f"{return_to}?{return_query}"

        session_date = parse_date(request.POST.get('date', ''))
        status = request.POST.get('status', TherapySession.STATUS_DONE)
        notes = (request.POST.get('notes') or '').strip()
        create_bill = (
            request.POST.get('create_bill') in {'true', '1', 'on'}
            or request.POST.get('action') == 'save_and_bill'
        )

        if not session_date or session_date > timezone.localdate():
            error_msg = 'Choose a valid session date that is not in the future.'
            if is_ajax:
                return JsonResponse({'error': error_msg}, status=400)
            messages.error(request, error_msg)
            return redirect(return_to)
        if status not in {TherapySession.STATUS_DONE, TherapySession.STATUS_MISSED}:
            error_msg = 'Choose Done or Missed for the session status.'
            if is_ajax:
                return JsonResponse({'error': error_msg}, status=400)
            messages.error(request, error_msg)
            return redirect(return_to)
        if create_bill and status != TherapySession.STATUS_DONE:
            error_msg = 'Only completed (Done) sessions can be billed.'
            if is_ajax:
                return JsonResponse({'error': error_msg}, status=400)
            messages.error(request, error_msg)
            return redirect(return_to)

        with transaction.atomic():
            prescribed = get_object_or_404(
                PrescriptionTherapy.objects.select_for_update().select_related(
                    'therapy', 'prescription__visit'
                ),
                pk=pk,
            )
            done_count = prescribed.session_records.filter(status=TherapySession.STATUS_DONE).count()
            if prescribed.status != 'active' or done_count >= prescribed.total_sessions:
                error_msg = 'All prescribed therapy sessions are already completed.'
                if is_ajax:
                    return JsonResponse({'error': error_msg}, status=400)
                messages.error(request, error_msg)
                return redirect(return_to)

            latest_number = prescribed.session_records.aggregate(number=Max('session_no'))['number'] or 0
            session = TherapySession.objects.create(
                prescription_therapy=prescribed,
                session_no=latest_number + 1,
                date=session_date,
                status=status,
                notes=notes,
                done_by=request.user.innermember,
            )

            bill = None
            if create_bill:
                payment_method = request.POST.get('payment_method', 'cash')
                session_price = prescribed.session_price or Decimal('0')
                line_items = [
                    {
                        'prescribed': prescribed,
                        'name': f"{prescribed.therapy.name} · Session {session.session_no}",
                        'billing_type': BILLING_TYPE_PER_SESSION,
                        'sessions': 1,
                        'unit_price': session_price,
                        'amount': session_price,
                    }
                ]
                bill = create_direct_therapy_bill(
                    visit=prescribed.prescription.visit,
                    payment_method=payment_method,
                    line_items=line_items,
                )
                session.bill = bill
                session.save(update_fields=['bill'])

            if status == TherapySession.STATUS_DONE and done_count + 1 >= prescribed.total_sessions:
                prescribed.status = 'completed'
                prescribed.save(update_fields=['status', 'updated_at'])

        if create_bill and bill:
            print_url = (
                reverse('billing:print_bill', args=[encode_id(prescribed.prescription.visit.id)])
                + f'?bill_id={encode_id(bill.id)}'
            )
            if is_ajax:
                return JsonResponse({
                    'success': True,
                    'message': f'{prescribed.therapy.name} session {session.session_no} saved and billed ({bill.bill_number}).',
                    'redirect_url': print_url,
                    'bill_number': bill.bill_number,
                })
            messages.success(
                request,
                f'{prescribed.therapy.name} session {session.session_no} saved and billed ({bill.bill_number}).',
            )
            return redirect(print_url)

        result = 'marked done' if status == TherapySession.STATUS_DONE else 'recorded as missed'
        success_msg = f'{prescribed.therapy.name} session {session.session_no} {result}.'

        if is_ajax:
            next_session_no = session.session_no + 1 if prescribed.status == 'active' else None
            return JsonResponse({
                'success': True,
                'message': success_msg,
                'status': prescribed.status,
                'progress_text': prescribed.progress_text,
                'progress_percent': prescribed.progress_percent,
                'last_session_date': session.date.strftime('%d %b %Y'),
                'next_session_no': next_session_no,
                'sessions_remaining': prescribed.sessions_remaining,
                'total_sessions': prescribed.total_sessions,
            })

        messages.success(request, success_msg)
        return redirect(return_to)


class BillTherapySessionsView(LoginRequiredMixin, BillingAccessMixin, View):
    login_url = 'doctor:login'

    def post(self, request, pk):
        is_ajax = (
            request.headers.get('x-requested-with') == 'XMLHttpRequest'
            or 'application/json' in request.headers.get('accept', '')
        )
        with transaction.atomic():
            prescribed = get_object_or_404(
                PrescriptionTherapy.objects.select_for_update().select_related(
                    'therapy', 'prescription__visit'
                ),
                pk=pk,
            )
            unbilled_sessions = list(
                prescribed.session_records.select_for_update().filter(
                    status=TherapySession.STATUS_DONE,
                    bill__isnull=True,
                ).order_by('session_no')
            )
            if not unbilled_sessions:
                error_msg = 'No unbilled sessions found.'
                if is_ajax:
                    return JsonResponse({'error': error_msg}, status=400)
                messages.error(request, error_msg)
                return redirect('doctor:therapy:therapy_sessions')

            payment_method = request.POST.get('payment_method', 'cash')
            session_price = prescribed.session_price or Decimal('0')
            line_items = [
                {
                    'prescribed': prescribed,
                    'name': f"{prescribed.therapy.name} · Session {s.session_no}",
                    'billing_type': BILLING_TYPE_PER_SESSION,
                    'sessions': 1,
                    'unit_price': session_price,
                    'amount': session_price,
                }
                for s in unbilled_sessions
            ]
            bill = create_direct_therapy_bill(
                visit=prescribed.prescription.visit,
                payment_method=payment_method,
                line_items=line_items,
            )
            for s in unbilled_sessions:
                s.bill = bill
                s.save(update_fields=['bill'])

        print_url = (
            reverse('billing:print_bill', args=[encode_id(prescribed.prescription.visit.id)])
            + f'?bill_id={encode_id(bill.id)}'
        )
        if is_ajax:
            return JsonResponse({
                'success': True,
                'message': f'Bill {bill.bill_number} created successfully.',
                'redirect_url': print_url,
                'bill_number': bill.bill_number,
            })
        messages.success(request, f'Bill {bill.bill_number} created successfully.')
        return redirect(print_url)


class BillTherapyPackageView(LoginRequiredMixin, BillingAccessMixin, View):
    login_url = 'doctor:login'

    def post(self, request, pk):
        is_ajax = (
            request.headers.get('x-requested-with') == 'XMLHttpRequest'
            or 'application/json' in request.headers.get('accept', '')
        )
        with transaction.atomic():
            prescribed = get_object_or_404(
                PrescriptionTherapy.objects.select_for_update().select_related(
                    'therapy', 'prescription__visit'
                ),
                pk=pk,
            )
            if prescribed.package_billed_id or prescribed.therapy_bill_items.filter(billing_type=BILLING_TYPE_PACKAGE).exists():
                error_msg = 'This package has already been billed.'
                if is_ajax:
                    return JsonResponse({'error': error_msg}, status=400)
                messages.error(request, error_msg)
                return redirect('doctor:therapy:therapy_sessions')

            payment_method = request.POST.get('payment_method', 'cash')
            package_price = prescribed.package_price or Decimal('0')
            sessions_count = prescribed.total_sessions
            sessions_label = f"{sessions_count} session{'s' if sessions_count != 1 else ''}"
            line_items = [
                {
                    'prescribed': prescribed,
                    'name': f"{prescribed.therapy.name} · Package ({sessions_label})",
                    'billing_type': BILLING_TYPE_PACKAGE,
                    'sessions': sessions_count,
                    'unit_price': package_price,
                    'amount': package_price,
                }
            ]
            bill = create_direct_therapy_bill(
                visit=prescribed.prescription.visit,
                payment_method=payment_method,
                line_items=line_items,
            )
            prescribed.package_billed = bill
            prescribed.save(update_fields=['package_billed'])

        print_url = (
            reverse('billing:print_bill', args=[encode_id(prescribed.prescription.visit.id)])
            + f'?bill_id={encode_id(bill.id)}'
        )
        if is_ajax:
            return JsonResponse({
                'success': True,
                'message': f'Package bill {bill.bill_number} created successfully.',
                'redirect_url': print_url,
                'bill_number': bill.bill_number,
            })
        messages.success(request, f'Package bill {bill.bill_number} created successfully.')
        return redirect(print_url)


class TherapySessionDetailView(LoginRequiredMixin, BillingAccessMixin, View):
    login_url = 'doctor:login'

    def get(self, request, pk):
        prescribed = get_object_or_404(
            PrescriptionTherapy.objects.select_related(
                'therapy', 'prescription__visit__patient__user',
                'prescription__visit__appointment__family_member',
            ).prefetch_related('session_records__done_by__user', 'session_records__bill'),
            pk=pk,
        )
        sessions = list(prescribed.session_records.all())
        sessions_by_number = {session.session_no: session for session in sessions}
        last_number = max(prescribed.total_sessions, max(sessions_by_number, default=0))
        timeline = [
            {'number': number, 'session': sessions_by_number.get(number)}
            for number in range(1, last_number + 1)
        ]
        last_done = next(
            (session for session in reversed(sessions) if session.status == TherapySession.STATUS_DONE),
            None,
        )
        undo_session_id = last_done.pk if last_done and not last_done.bill_id else None
        patient_name = (
            prescribed.prescription.visit.appointment.family_member.name
            if prescribed.prescription.visit.appointment.family_member
            else prescribed.prescription.visit.patient.user.get_full_name()
            or prescribed.prescription.visit.patient.user.username
        )
        return render(request, 'therapy/session_detail.html', {
            'prescribed': prescribed,
            'timeline': timeline,
            'patient_name': patient_name,
            'undo_session_id': undo_session_id,
        })


class UndoTherapySessionView(LoginRequiredMixin, BillingAccessMixin, View):
    login_url = 'doctor:login'

    def post(self, request, session_pk):
        session_ref = get_object_or_404(TherapySession, pk=session_pk)
        detail_url = redirect(
            'doctor:therapy:therapy_session_detail',
            pk=session_ref.prescription_therapy_id,
        ).url
        return_to = request.POST.get('return_to', detail_url)
        if not return_to.startswith('/') or return_to.startswith('//'):
            return_to = detail_url
        with transaction.atomic():
            prescribed = get_object_or_404(
                PrescriptionTherapy.objects.select_for_update(),
                pk=session_ref.prescription_therapy_id,
            )
            session = get_object_or_404(
                TherapySession.objects.select_for_update().filter(prescription_therapy=prescribed),
                pk=session_pk,
                status=TherapySession.STATUS_DONE,
            )
            if session.bill_id:
                messages.error(request, 'This billed session cannot be undone.')
                return redirect(return_to)

            last_done_id = prescribed.session_records.filter(
                status=TherapySession.STATUS_DONE
            ).order_by('-session_no').values_list('pk', flat=True).first()
            if last_done_id != session.pk:
                messages.error(request, 'Only the latest done session can be undone.')
                return redirect(return_to)

            session.delete()
            if prescribed.status == 'completed' and prescribed.sessions_done < prescribed.total_sessions:
                prescribed.status = 'active'
                prescribed.save(update_fields=['status', 'updated_at'])

        messages.success(request, 'The latest session was undone.')
        return redirect(return_to)


class DeleteTherapySessionView(LoginRequiredMixin, BillingAccessMixin, View):
    login_url = 'doctor:login'

    def post(self, request, pk):
        prescribed = get_object_or_404(PrescriptionTherapy, pk=pk)
        session_pk = request.POST.get('session_id')
        detail_url = redirect('doctor:therapy:therapy_session_detail', pk=pk).url
        return_to = request.POST.get('return_to', request.GET.get('return_to', '/doctor/therapies/sessions/'))
        if not return_to.startswith('/') or return_to.startswith('//'):
            return_to = '/doctor/therapies/sessions/'
        with transaction.atomic():
            prescribed = get_object_or_404(PrescriptionTherapy.objects.select_for_update(), pk=pk)
            session = get_object_or_404(TherapySession.objects.select_for_update(), pk=session_pk, prescription_therapy=prescribed)
            if session.bill_id:
                messages.error(request, 'Billed sessions cannot be deleted.')
                return redirect(return_to)
            session.delete()
            for idx, s in enumerate(prescribed.session_records.order_by('date', 'pk'), start=1):
                if s.session_no != idx:
                    s.session_no = idx
                    s.save(update_fields=['session_no'])
            if prescribed.status == 'completed' and prescribed.sessions_done < prescribed.total_sessions:
                prescribed.status = 'active'
                prescribed.save(update_fields=['status', 'updated_at'])
        messages.success(request, 'Session deleted successfully.')
        return redirect(return_to)


class RemoveTherapyView(LoginRequiredMixin, View):
    login_url = 'doctor:login'

    def get(self, request, pk):
        return HttpResponseNotAllowed(['POST'])

    def post(self, request, pk):
        member = getattr(request.user, 'innermember', None)
        if not member or (member.role != 'doctor' and not member.is_owner):
            messages.error(request, 'Only a doctor or clinic owner can remove therapies.')
            return redirect('doctor:therapy:therapy_sessions')

        return_to = request.POST.get('return_to', request.GET.get('return_to', ''))
        return_query = request.POST.get('return_query', '')
        if return_query and '?' not in return_to:
            return_to = f"{return_to}?{return_query}"
        if not return_to or not return_to.startswith('/') or return_to.startswith('//'):
            query_str = request.GET.urlencode()
            base_url = reverse('doctor:therapy:therapy_sessions')
            return_to = f"{base_url}?{query_str}" if query_str else base_url

        with transaction.atomic():
            prescribed = get_object_or_404(
                PrescriptionTherapy.objects.select_for_update().select_related('therapy'),
                pk=pk,
            )
            has_billed_sessions = prescribed.session_records.filter(bill__isnull=False).exists()
            has_billed_package = bool(prescribed.package_billed_id) or prescribed.therapy_bill_items.filter(
                billing_type=BILLING_TYPE_PACKAGE, bill__isnull=False
            ).exists()
            has_billed_items = prescribed.therapy_bill_items.filter(bill__isnull=False).exists()

            anything_billed = has_billed_sessions or has_billed_package or has_billed_items

            if not anything_billed:
                therapy_name = prescribed.therapy.name
                prescribed.session_records.all().delete()
                prescribed.delete()
                messages.success(request, f"Therapy '{therapy_name}' and all its sessions were removed.")
            else:
                prescribed.status = 'cancelled'
                prescribed.save(update_fields=['status', 'updated_at'])
                messages.success(request, f"Therapy '{prescribed.therapy.name}' was stopped and marked as cancelled.")

        return redirect(return_to)


class CompleteEarlyView(LoginRequiredMixin, View):
    login_url = 'doctor:login'

    def get(self, request, pk):
        return HttpResponseNotAllowed(['POST'])

    def post(self, request, pk):
        member = getattr(request.user, 'innermember', None)
        if not member or (member.role != 'doctor' and not member.is_owner):
            messages.error(request, 'Only a doctor or clinic owner can complete therapies early.')
            return redirect('doctor:therapy:therapy_sessions')

        return_to = request.POST.get('return_to', request.GET.get('return_to', ''))
        return_query = request.POST.get('return_query', '')
        if return_query and '?' not in return_to:
            return_to = f"{return_to}?{return_query}"
        if not return_to or not return_to.startswith('/') or return_to.startswith('//'):
            query_str = request.GET.urlencode()
            base_url = reverse('doctor:therapy:therapy_sessions')
            return_to = f"{base_url}?{query_str}" if query_str else base_url

        with transaction.atomic():
            prescribed = get_object_or_404(
                PrescriptionTherapy.objects.select_for_update().select_related('therapy'),
                pk=pk,
            )
            if prescribed.status != 'active':
                messages.error(request, f"Therapy '{prescribed.therapy.name}' is not active.")
                return redirect(return_to)

            done_count = prescribed.session_records.filter(status=TherapySession.STATUS_DONE).count()
            if done_count < 1:
                messages.error(request, 'At least one session must be done before completing early.')
                return redirect(return_to)

            prescribed.total_sessions = done_count
            prescribed.status = 'completed'
            prescribed.save(update_fields=['total_sessions', 'status', 'updated_at'])
            messages.success(
                request,
                f"Therapy '{prescribed.therapy.name}' completed early at {done_count}/{done_count} sessions."
            )

        return redirect(return_to)
