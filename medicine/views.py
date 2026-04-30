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
        
        paginator = Paginator(medicines_list, 20) # Show 20 medicines per page
        page_number = request.GET.get('page')
        medicines = paginator.get_page(page_number)
        
        return render(request, 'medicine/manage_medicine.html', {'medicines': medicines})


class AddMedicineView(LoginRequiredMixin, View):
    login_url = 'doctor:login'

    def get(self, request):
        medicine_types = Medicine.MEDICINE_TYPE
        return render(request, 'medicine/add_medicine1.html', {'medicine_types': medicine_types})

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

        # Dynamic variants from POST (power[], price[], stock[], low_stock_alert[])
        powers      = request.POST.getlist('power[]')
        prices      = request.POST.getlist('price[]')
        stocks      = request.POST.getlist('stock[]')
        low_alerts  = request.POST.getlist('low_stock_alert[]')

        for i, power in enumerate(powers):
            if power.strip():
                MedicineVariant.objects.create(
                    medicine=medicine,
                    power=power.strip(),
                    price=prices[i] if i < len(prices) else 0,
                    stock=stocks[i] if i < len(stocks) else 0,
                    low_stock_alert=low_alerts[i] if i < len(low_alerts) else 10,
                )

        return redirect('medicine:manage_medicine')


class DeleteMedicineView(LoginRequiredMixin, View):
    login_url = 'doctor:login'

    def post(self, request, pk):
        medicine = get_object_or_404(Medicine, pk=pk)
        medicine.delete()  # variants bhi cascade delete honge
        return redirect('medicine:manage_medicine')


class EditMedicineView(LoginRequiredMixin, View):
    login_url = 'doctor:login'

    def get(self, request, pk):
        medicine = get_object_or_404(Medicine, pk=pk)
        medicine_types = Medicine.MEDICINE_TYPE
        return render(request, 'medicine/edit_medicine.html', {
            'medicine': medicine,
            'medicine_types': medicine_types,
        })

    def post(self, request, pk):
        medicine = get_object_or_404(Medicine, pk=pk)
        medicine.name        = request.POST.get('name', '').strip()
        medicine.short_name  = request.POST.get('short_name', '').strip()
        medicine.medicine_type = request.POST.get('medicine_type', '')
        medicine.company     = request.POST.get('company', '').strip()
        medicine.description = request.POST.get('description', '').strip()
        medicine.is_active   = request.POST.get('is_active') == 'on'
        medicine.save()

        # Delete removed variants (client sends kept variant IDs)
        kept_ids = request.POST.getlist('variant_id[]')
        medicine.variants.exclude(pk__in=[i for i in kept_ids if i]).delete()

        # Update existing variants
        variant_ids    = request.POST.getlist('variant_id[]')
        powers         = request.POST.getlist('power[]')
        prices         = request.POST.getlist('price[]')
        stocks         = request.POST.getlist('stock[]')
        low_alerts     = request.POST.getlist('low_stock_alert[]')

        for i, vid in enumerate(variant_ids):
            if vid:  # existing variant — update
                try:
                    variant = MedicineVariant.objects.get(pk=vid, medicine=medicine)
                    variant.power           = powers[i].strip()
                    variant.price           = prices[i]
                    variant.stock           = stocks[i]
                    variant.low_stock_alert = low_alerts[i]
                    variant.save()
                except MedicineVariant.DoesNotExist:
                    pass
            else:  # new variant (vid is empty string)
                if powers[i].strip():
                    MedicineVariant.objects.create(
                        medicine=medicine,
                        power=powers[i].strip(),
                        price=prices[i],
                        stock=stocks[i],
                        low_stock_alert=low_alerts[i],
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
                    'price': str(v.price),
                    'stock': v.stock,
                    'is_low_stock': v.is_low_stock,
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