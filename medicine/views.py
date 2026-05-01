from django.shortcuts import render, redirect, get_object_or_404
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.db.models import Q
from .models import Medicine, MedicineVariant
from django.core.paginator import Paginator


class ManageMedicineView(LoginRequiredMixin, View):
    login_url = 'doctor:login'

    def get(self, request):
        medicines_list = Medicine.objects.prefetch_related('variants').all().order_by('-created_at')
        paginator = Paginator(medicines_list, 20)
        page_number = request.GET.get('page')
        medicines = paginator.get_page(page_number)
        return render(request, 'medicine/manage_medicine.html', {'medicines': medicines})


class AddMedicineView(LoginRequiredMixin, View):
    login_url = 'doctor:login'

    def get(self, request):
        medicine_types = Medicine.MEDICINE_TYPE
        unit_choices = MedicineVariant.UNIT_CHOICES
        return render(request, 'medicine/add_medicine1.html', {
            'medicine_types': medicine_types,
            'unit_choices': unit_choices,
        })

    def post(self, request):
        name        = request.POST.get('name', '').strip()
        short_name  = request.POST.get('short_name', '').strip()
        med_type    = request.POST.get('medicine_type', '')
        company     = request.POST.get('company', '').strip()
        description = request.POST.get('description', '').strip()
        is_active   = request.POST.get('is_active') == 'on'

        medicine = Medicine.objects.create(
            name=name,
            short_name=short_name,
            medicine_type=med_type,
            company=company,
            description=description,
            is_active=is_active,
        )

        powers          = request.POST.getlist('power[]')
        cost_prices     = request.POST.getlist('cost_price[]')
        selling_prices  = request.POST.getlist('selling_price[]')
        stocks          = request.POST.getlist('stock[]')
        units           = request.POST.getlist('unit[]')
        unit_per_strips = request.POST.getlist('unit_per_strip[]')
        low_alerts      = request.POST.getlist('low_stock_alert[]')
        mfg_dates       = request.POST.getlist('mfg_date[]')
        exp_dates       = request.POST.getlist('exp_date[]')

        for i, power in enumerate(powers):
            if power.strip():
                MedicineVariant.objects.create(
                    medicine=medicine,
                    power=power.strip(),
                    cost_price=cost_prices[i] if i < len(cost_prices) else 0,
                    selling_price=selling_prices[i] if i < len(selling_prices) else 0,
                    stock=stocks[i] if i < len(stocks) else 0,
                    unit=units[i] if i < len(units) else 'piece',
                    unit_per_strip=unit_per_strips[i] if i < len(unit_per_strips) and unit_per_strips[i] else None,
                    low_stock_alert=low_alerts[i] if i < len(low_alerts) else 10,
                    mfg_date=mfg_dates[i] if i < len(mfg_dates) and mfg_dates[i] else None,
                    exp_date=exp_dates[i] if i < len(exp_dates) and exp_dates[i] else None,
                )

        return redirect('medicine:manage_medicine')


class DeleteMedicineView(LoginRequiredMixin, View):
    login_url = 'doctor:login'

    def post(self, request, pk):
        medicine = get_object_or_404(Medicine, pk=pk)
        medicine.delete()
        return redirect('medicine:manage_medicine')


class EditMedicineView(LoginRequiredMixin, View):
    login_url = 'doctor:login'

    def get(self, request, pk):
        medicine = get_object_or_404(Medicine, pk=pk)
        medicine_types = Medicine.MEDICINE_TYPE
        unit_choices = MedicineVariant.UNIT_CHOICES
        return render(request, 'medicine/edit_medicine.html', {
            'medicine': medicine,
            'medicine_types': medicine_types,
            'unit_choices': unit_choices,
        })

    def post(self, request, pk):
        medicine = get_object_or_404(Medicine, pk=pk)
        medicine.name          = request.POST.get('name', '').strip()
        medicine.short_name    = request.POST.get('short_name', '').strip()
        medicine.medicine_type = request.POST.get('medicine_type', '')
        medicine.company       = request.POST.get('company', '').strip()
        medicine.description   = request.POST.get('description', '').strip()
        medicine.is_active     = request.POST.get('is_active') == 'on'
        medicine.save()

        kept_ids = request.POST.getlist('variant_id[]')
        medicine.variants.exclude(pk__in=[i for i in kept_ids if i]).delete()

        variant_ids     = request.POST.getlist('variant_id[]')
        powers          = request.POST.getlist('power[]')
        cost_prices     = request.POST.getlist('cost_price[]')
        selling_prices  = request.POST.getlist('selling_price[]')
        stocks          = request.POST.getlist('stock[]')
        units           = request.POST.getlist('unit[]')
        unit_per_strips = request.POST.getlist('unit_per_strip[]')
        low_alerts      = request.POST.getlist('low_stock_alert[]')
        mfg_dates       = request.POST.getlist('mfg_date[]')
        exp_dates       = request.POST.getlist('exp_date[]')

        for i, vid in enumerate(variant_ids):
            if vid:
                try:
                    variant = MedicineVariant.objects.get(pk=vid, medicine=medicine)
                    variant.power          = powers[i].strip()
                    variant.cost_price     = cost_prices[i]
                    variant.selling_price  = selling_prices[i]
                    variant.stock          = stocks[i]
                    variant.unit           = units[i]
                    variant.unit_per_strip = unit_per_strips[i] if unit_per_strips[i] else None
                    variant.low_stock_alert = low_alerts[i]
                    variant.mfg_date       = mfg_dates[i] if mfg_dates[i] else None
                    variant.exp_date       = exp_dates[i] if exp_dates[i] else None
                    variant.save()
                except MedicineVariant.DoesNotExist:
                    pass
            else:
                if powers[i].strip():
                    MedicineVariant.objects.create(
                        medicine=medicine,
                        power=powers[i].strip(),
                        cost_price=cost_prices[i],
                        selling_price=selling_prices[i],
                        stock=stocks[i],
                        unit=units[i],
                        unit_per_strip=unit_per_strips[i] if unit_per_strips[i] else None,
                        low_stock_alert=low_alerts[i],
                        mfg_date=mfg_dates[i] if mfg_dates[i] else None,
                        exp_date=exp_dates[i] if exp_dates[i] else None,
                    )

        return redirect('medicine:manage_medicine')


class MedicineSearchView(LoginRequiredMixin, View):
    login_url = 'doctor:login'

    def get(self, request):
        query = request.GET.get('q', '').strip()

        if len(query) < 2:
            return JsonResponse({'medicines': []})

        medicines = Medicine.objects.filter(
            Q(name__icontains=query) |
            Q(short_name__icontains=query) |
            Q(company__icontains=query)
        ).prefetch_related('variants').filter(is_active=True)[:10]

        data = []
        for med in medicines:
            variants = [
                {
                    'id': v.id,
                    'power': v.power,
                    'price': str(v.selling_price),  # ← selling_price use karo
                    'stock': v.stock,
                    'is_low_stock': v.is_low_stock,
                    'is_expired': v.is_expired,
                }
                for v in med.variants.all()
            ]
            data.append({
                'id': med.id,
                'name': med.name,
                'short_name': med.short_name,
                'type': med.get_medicine_type_display(),
                'company': med.company,
                'variants': variants,
            })

        return JsonResponse({'medicines': data})