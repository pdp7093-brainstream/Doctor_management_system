from django.shortcuts import render, redirect, get_object_or_404
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.db.models import Q
from .models import *
from django.core.paginator import Paginator
from django.db import models as db_models
from django.contrib import messages
from django.contrib.auth.decorators import login_required

class ManageMedicineView(LoginRequiredMixin, View):
    login_url = "doctor:login"

    def get(self, request):
        medicines_list = (
            Medicine.objects.prefetch_related("variants").all().order_by("-created_at")
        )
        paginator = Paginator(medicines_list, 20)
        page_number = request.GET.get("page")
        medicines = paginator.get_page(page_number)
        return render(
            request, "medicine/manage_medicine.html", {"medicines": medicines}
        )


class AddMedicineView(LoginRequiredMixin, View):
    login_url = "doctor:login"

    def get(self, request):
        medicine_types = Medicine.MEDICINE_TYPE
        unit_choices = MedicineVariant.UNIT_CHOICES
        return render(
            request,
            "medicine/add_medicine1.html",
            {
                "medicine_types": medicine_types,
                "unit_choices": unit_choices,
            },
        )

    def post(self, request):
        name = request.POST.get("name", "").strip()
        short_name = request.POST.get("short_name", "").strip()
        med_type = request.POST.get("medicine_type", "")
        company = request.POST.get("company", "").strip()
        description = request.POST.get("description", "").strip()
        is_active = request.POST.get("is_active") == "on"

        medicine = Medicine.objects.create(
            name=name,
            short_name=short_name,
            medicine_type=med_type,
            company=company,
            description=description,
            is_active=is_active,
        )

        powers = request.POST.getlist("power[]")
        cost_prices = request.POST.getlist("cost_price[]")
        selling_prices = request.POST.getlist("selling_price[]")
        stocks = request.POST.getlist("stock[]")  # JS-computed hidden field
        total_strips_list = request.POST.getlist(
            "total_strips[]"
        )  # UI-only convenience field
        units = request.POST.getlist("unit[]")
        unit_per_strips = request.POST.getlist("unit_per_strip[]")
        low_alerts = request.POST.getlist("low_stock_alert[]")
        mfg_dates = request.POST.getlist("mfg_date[]")
        exp_dates = request.POST.getlist("exp_date[]")

        for i, power in enumerate(powers):
            if not power.strip():
                continue

            ups_raw = (
                unit_per_strips[i]
                if i < len(unit_per_strips) and unit_per_strips[i]
                else None
            )
            ups = int(ups_raw) if ups_raw else 0

            # Prefer JS-calculated stock; fall back to server-side calculation from strips
            stock_raw = stocks[i] if i < len(stocks) and stocks[i] else "0"
            computed_stock = int(stock_raw) if stock_raw else 0
            if computed_stock == 0 and ups > 0:
                ts_raw = (
                    total_strips_list[i]
                    if i < len(total_strips_list) and total_strips_list[i]
                    else "0"
                )
                computed_stock = int(ts_raw) * ups

            MedicineVariant.objects.create(
                medicine=medicine,
                power=power.strip(),
                cost_price=cost_prices[i] if i < len(cost_prices) else 0,
                selling_price=selling_prices[i] if i < len(selling_prices) else 0,
                stock=computed_stock,
                unit=units[i] if i < len(units) else "piece",
                unit_per_strip=ups if ups > 0 else None,
                low_stock_alert=low_alerts[i] if i < len(low_alerts) else 10,
                mfg_date=mfg_dates[i] if i < len(mfg_dates) and mfg_dates[i] else None,
                exp_date=exp_dates[i] if i < len(exp_dates) and exp_dates[i] else None,
            )

        return redirect("medicine:manage_medicine")


class DeleteMedicineView(LoginRequiredMixin, View):
    login_url = "doctor:login"

    def post(self, request, pk):
        medicine = get_object_or_404(Medicine, pk=pk)
        medicine.delete()
        return redirect("medicine:manage_medicine")


class EditMedicineView(LoginRequiredMixin, View):
    login_url = "doctor:login"

    def get(self, request, pk):
        medicine = get_object_or_404(Medicine, pk=pk)
        medicine_types = Medicine.MEDICINE_TYPE
        unit_choices = MedicineVariant.UNIT_CHOICES
        return render(
            request,
            "medicine/edit_medicine.html",
            {
                "medicine": medicine,
                "medicine_types": medicine_types,
                "unit_choices": unit_choices,
            },
        )

    def post(self, request, pk):
        medicine = get_object_or_404(Medicine, pk=pk)
        medicine.name = request.POST.get("name", "").strip()
        medicine.short_name = request.POST.get("short_name", "").strip()
        medicine.medicine_type = request.POST.get("medicine_type", "")
        medicine.company = request.POST.get("company", "").strip()
        medicine.description = request.POST.get("description", "").strip()
        medicine.is_active = request.POST.get("is_active") == "on"
        medicine.save()

        kept_ids = request.POST.getlist("variant_id[]")
        medicine.variants.exclude(pk__in=[i for i in kept_ids if i]).delete()

        variant_ids = request.POST.getlist("variant_id[]")
        powers = request.POST.getlist("power[]")
        cost_prices = request.POST.getlist("cost_price[]")
        selling_prices = request.POST.getlist("selling_price[]")
        stocks = request.POST.getlist("stock[]")  # JS-computed hidden field
        total_strips_list = request.POST.getlist(
            "total_strips[]"
        )  # UI-only convenience field
        units = request.POST.getlist("unit[]")
        unit_per_strips = request.POST.getlist("unit_per_strip[]")
        low_alerts = request.POST.getlist("low_stock_alert[]")
        mfg_dates = request.POST.getlist("mfg_date[]")
        exp_dates = request.POST.getlist("exp_date[]")

        for i, vid in enumerate(variant_ids):
            ups_raw = (
                unit_per_strips[i]
                if i < len(unit_per_strips) and unit_per_strips[i]
                else None
            )
            ups = int(ups_raw) if ups_raw else 0

            # Prefer JS-calculated stock; fall back to server-side calculation from strips
            stock_raw = stocks[i] if i < len(stocks) and stocks[i] else "0"
            computed_stock = int(stock_raw) if stock_raw else 0
            if computed_stock == 0 and ups > 0:
                ts_raw = (
                    total_strips_list[i]
                    if i < len(total_strips_list) and total_strips_list[i]
                    else "0"
                )
                computed_stock = int(ts_raw) * ups

            if vid:
                try:
                    variant = MedicineVariant.objects.get(pk=vid, medicine=medicine)
                    variant.power = powers[i].strip()
                    variant.cost_price = cost_prices[i]
                    variant.selling_price = selling_prices[i]
                    variant.stock = computed_stock
                    variant.unit = units[i]
                    variant.unit_per_strip = ups if ups > 0 else None
                    variant.low_stock_alert = low_alerts[i]
                    variant.mfg_date = mfg_dates[i] if mfg_dates[i] else None
                    variant.exp_date = exp_dates[i] if exp_dates[i] else None
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
                        stock=computed_stock,
                        unit=units[i],
                        unit_per_strip=ups if ups > 0 else None,
                        low_stock_alert=low_alerts[i],
                        mfg_date=mfg_dates[i] if mfg_dates[i] else None,
                        exp_date=exp_dates[i] if exp_dates[i] else None,
                    )

        return redirect("medicine:manage_medicine")


class MedicineSearchView(LoginRequiredMixin, View):
    login_url = "doctor:login"

    def get(self, request):
        query = request.GET.get("q", "").strip()

        if len(query) < 2:
            return JsonResponse({"medicines": []})

        medicines = (
            Medicine.objects.filter(
                Q(name__icontains=query)
                | Q(short_name__icontains=query)
                | Q(company__icontains=query)
            )
            .prefetch_related("variants")
            .filter(is_active=True)[:10]
        )

        data = []
        for med in medicines:
            variants = [
                {
                    "id": v.id,
                    "power": v.power,
                    "price": str(v.selling_price),  # ← selling_price use karo
                    "stock": v.stock,
                    "is_low_stock": v.is_low_stock,
                    "is_expired": v.is_expired,
                }
                for v in med.variants.all()
            ]
            data.append(
                {
                    "id": med.id,
                    "name": med.name,
                    "short_name": med.short_name,
                    "type": med.get_medicine_type_display(),
                    "company": med.company,
                    "variants": variants,
                }
            )

        return JsonResponse({"medicines": data})


@login_required(login_url="doctor:login")
def search_medicine(request):
    query = request.GET.get("q", "").strip()

    if not query:
        return JsonResponse([], safe=False)

    variants = (
        MedicineVariant.objects.select_related("medicine")
        .filter(
            Q(medicine__name__icontains=query)
            | Q(medicine__short_name__icontains=query)
            | Q(medicine__company__icontains=query),
            medicine__is_active=True,
        )
        .order_by("medicine__name", "power")[:10]
    )

    data = [
        {
            "id": variant.id,
            "name": variant.medicine.name,
            "short_name": variant.medicine.short_name,
            "company": variant.medicine.company,
            "power": variant.power,
        }
        for variant in variants
    ]

    if request.GET.get("grouped") == "1":
        grouped = {}
        for variant in variants:
            medicine = variant.medicine
            grouped.setdefault(
                medicine.id,
                {
                    "id": medicine.id,
                    "name": medicine.name,
                    "short_name": medicine.short_name,
                    "type": medicine.get_medicine_type_display(),
                    "company": medicine.company,
                    "variants": [],
                },
            )["variants"].append(
                {
                    "id": variant.id,
                    "power": variant.power,
                    "price": str(variant.selling_price),
                    "stock": variant.stock,
                    "is_low_stock": variant.is_low_stock,
                    "is_expired": variant.is_expired,
                }
            )
        return JsonResponse({"medicines": list(grouped.values())})

    return JsonResponse(data, safe=False)


class LowStockView(LoginRequiredMixin, View):
    login_url = "doctor:login"

    def get(self, request):
        low_stock_variants = (
            MedicineVariant.objects.filter(
                stock__lte=db_models.F("low_stock_alert"), medicine__is_active=True
            )
            .select_related("medicine")
            .order_by("stock")
        )

        out_of_stock_count = low_stock_variants.filter(stock=0).count()

        return render(
            request,
            "medicine/low_stock.html",
            {
                "variants": low_stock_variants,
                "count": low_stock_variants.count(),
                "out_of_stock_count": out_of_stock_count,
            },
        )



def low_stock_count(request):
    # Fixed: 'low_stock_alerts' changed to 'low_stock_alert'
    count = MedicineVariant.objects.filter(
        stock__lte=db_models.F("low_stock_alert"), 
        medicine__is_active=True
    ).count()
    return JsonResponse({"count": count})

def low_stock_list(request):
    # Base queryset
    base_query = MedicineVariant.objects.filter(
        stock__lte=db_models.F("low_stock_alert"), 
        medicine__is_active=True
    )
    
    # Get total count for the whole system
    total_count = base_query.count()
    
    # Get just the top 10 for the UI
    variants = base_query.select_related("medicine").order_by("stock")[:10]

    data = [
        {
            "name": v.medicine.name,
            "power": v.power,
            "stock": v.stock,
            "low_alert": v.low_stock_alert,
            "is_out": v.stock == 0,
        }
        for v in variants
    ]
    
    return JsonResponse({
        "alerts": data, 
        "count": total_count  # Now returns the true total
    })



class VendorListView(LoginRequiredMixin, View):
    login_url = 'doctor:login'

    def get(self,request):
        vendors = Vendor.objects.all().order_by('name')
        return render(request,'medicine/vendor_list.html',{'vendors':vendors})
    

class AddVendorView(LoginRequiredMixin,View):
    login_url = 'doctor:login'

    def get(self,request):
        return render(request,'medicine/add_vendor.html')

    def post(self,request):
        name = request.POST.get('name','').strip()
        phone = request.POST.get('phone','').strip()
        email = request.POST.get('email','').strip()
        address = request.POST.get('address','').strip()

        Vendor.objects.create(
            name=name,
            phone = phone,
            email=email,
            address = address,
        )
        messages.success(request, f'Vendor "{name}" added successfully!')
        return redirect('medicine/vendor_list')


class EditVendorView(LoginRequiredMixin,View):
    login_url = "doctor:login"

    def get(self,request,pk):
        vendor= get_object_or_404(Vendor,pk=pk)
        return render(request, 'medicine/edit_vendor.html',{'vendor':vendor})

    def post(self,request,pk):
        vendor = get_object_or_404(Vendor,pk =pk)
        vendor.name = request.POST.get('name','').strip()
        vendor.phone = request.POST.get('phone','').strip()
        vendor.email = request.POST.get('email','').strip()
        vendor.address = request.POST.get('address','').strip()
        vendor.save()

        messages.success(request, f'Vendor "{vendor.name}" updated!')
        return redirect('medicine:vendor_list')
    
class DeleteVendorView(LoginRequiredMixin,View):
    login_url = 'doctor:login'

    def post(self,request,pk):
        vendor = get_object_or_404(Vendor,pk=pk)
        name = vendor.name 
        vendor.delete()
        messages.success(request, f'Vendor "{name}" deleted!')



# Purchase Views 
class PurchaseListView(LoginRequiredMixin,View):
    login_url = 'doctor:login'

    def get(self,request):
        purchases = Purchase.objects.select_related('vendor').order_by('-date')
        return render(request, 'medicine/purchase_list.html',{'purchases':purchases})


class AddPurchaseView(LoginRequiredMixin,View):
    login_url = 'doctor:login'

    def get(self,request):
        vendors = Vendor.objects.all().order_by('name')
        return render(request, 'medicine/add_purchase.html',{
            'vendors': vendors,
        })

    
    def post(self,request):
        vendor_id = request.POST.get('vendor')
        vendor = get_object_or_404(Vendor,pk=vendor_id)

        variant_ids = request.POST.getlist('variant_id[]')
        qty_strips_list = request.POST.getlist('quantity_strips[]')
        ups_list = request.POST.getlist('unit_per_strip[]')
        cost_list = request.POST.getlist('cost_strip[]')

        # Validation 

        if not any(variant_ids):
            messages.error(request, 'Please add at least one medicine!')
            return redirect('medicine:add_purchase')
        
        total_amount = 0

        #Purchase create 
        purchase = Purchase.objects.create(
            vendor = vendor ,
            total_amount = 0 
        )

        for v_id, qty_str, ups_str, cost_str in zip(
            variant_ids, qty_strips_list,ups_list,cost_list
        ):
            if not v_id:
                continue 

            variant = get_object_or_404(MedicineVariant, pk=v_id)
            qty_strips = int(qty_str) if qty_str else 0
            ups = int(ups_str) if ups_str else 1 
            cost_strip = float(cost_str) if cost_str else 0 


            # Puchase item save karo 
            PurchaseItem.objects.create(
                purchase = purchase, 
                medicine_variant = variant, 
                quantity_strips = qty_strips, 
                unit_per_strip = ups,
                cost_strip = cost_strip,
            )

            # Stock Update 
            total_units = qty_strips * ups 
            variant.stock += total_units 
            variant.cost_price = cost_strip/ups if ups else cost_strip 
            variant.unit_per_strip = ups 
            variant.save()

            total_amount += qty_strips * cost_strip

        # Total update karo 
        purchase.total_amount = total_amount 
        purchase.save()

        messages.success(request, f'Purchase added! Total : {total_amount:.2f}')
        return redirect('medicine:purchase_list')
    
class PurchaseDetailView(LoginRequiredMixin, View):
    login_url = 'doctor:login'

    def get(self, request, pk):
        purchase = get_object_or_404(
            Purchase.objects.select_related('vendor').prefetch_related(
                'items__medicine_variant__medicine'
            ), pk=pk
        )
        return render(request, 'medicine/purchase_detail.html', {'purchase': purchase})
