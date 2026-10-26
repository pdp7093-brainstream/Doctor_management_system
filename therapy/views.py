from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count
from django.http import HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View

from .models import Therapy


def parse_non_negative_int(value, fallback=0):
    try:
        parsed = int(value)
        return parsed if parsed >= 0 else fallback
    except (TypeError, ValueError):
        return fallback


def therapy_form_values(request):
    name = request.POST.get('name', '').strip()
    try:
        price = Decimal(request.POST.get('price_per_session', '0').strip() or '0')
    except (InvalidOperation, AttributeError):
        price = None
    return {
        'name': name,
        'description': request.POST.get('description', '').strip(),
        'duration_minutes': parse_non_negative_int(request.POST.get('duration_minutes'), 45),
        'price_per_session': price,
        'is_active': request.POST.get('is_active') == 'on',
        'sort_order': parse_non_negative_int(request.POST.get('sort_order')),
    }


class TherapyListView(LoginRequiredMixin, View):
    login_url = 'doctor:login'

    def get(self, request):
        therapies = Therapy.objects.annotate(
            prescribed_count=Count('prescriptiontherapy__prescription', distinct=True)
        ).order_by('sort_order', 'name')
        return render(request, 'therapy/therapy_list.html', {'therapies': therapies})

    def post(self, request):
        values = therapy_form_values(request)
        if not values['name']:
            messages.error(request, 'Therapy name is required.')
        elif Therapy.objects.filter(name__iexact=values['name']).exists():
            messages.error(request, f"Therapy '{values['name']}' already exists.")
        elif values['price_per_session'] is None:
            messages.error(request, 'Enter a valid price per session.')
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
        elif values['price_per_session'] is None:
            messages.error(request, 'Enter a valid price per session.')
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