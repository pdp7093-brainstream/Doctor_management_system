from django.shortcuts import render, redirect, get_object_or_404
from doctor import hashid as _hashid
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponse, HttpResponseForbidden, JsonResponse, HttpResponseNotAllowed
from django.db.models import Q, Exists, OuterRef, Subquery, Count, F
from .models import *
from django.core.paginator import Paginator
from django.db import models as db_models
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from doctor.mixins import StaffRequiredMixin, has_staff_access
from django.utils import timezone
from decimal import Decimal
import hashlib
from io import BytesIO
from .services.medicine_importer import (
    MissingRequiredHeaders,
    generate_error_excel,
    generate_sample_excel,
    import_medicine_rows,
    import_names_only_rows,
    parse_medicine_excel,
    parse_names_only_excel,
)


def variant_price_error(cost_prices, selling_prices, free_samples, powers):
    for index, power in enumerate(powers):
        if not power.strip():
            continue
        try:
            cost = Decimal(cost_prices[index])
            selling = Decimal(selling_prices[index])
        except (IndexError, ArithmeticError, ValueError):
            return f"Variant {index + 1}: enter valid cost and selling prices."
        if not cost.is_finite() or not selling.is_finite():
            return f"Variant {index + 1}: enter valid cost and selling prices."
        is_free_sample = str(index) in free_samples
        if selling <= 0 or (not is_free_sample and selling < cost):
            return f"Variant {index + 1}: selling price must be greater than zero; unless marked Free / sample, it must not be less than cost price."
    return None

class ManageMedicineView(LoginRequiredMixin, StaffRequiredMixin, View):
    login_url = "doctor:login"

    def get(self, request):
        selected_type = request.GET.get("type", "").strip()
        if selected_type:
            try:
                selected_type = str(int(selected_type))
            except ValueError:
                selected_type = ""
            if selected_type and not MedicineType.objects.filter(pk=selected_type).exists():
                selected_type = ""
        selected_company = request.GET.get("company", "").strip()
        selected_pack = request.GET.get("pack", "").strip()
        if selected_pack not in {"complete", "incomplete"}:
            selected_pack = ""
        selected_stock = request.GET.get("stock", "").strip()
        if selected_stock not in {"in_stock", "low", "out"}:
            selected_stock = ""
        selected_status = request.GET.get("status", "").strip()
        if selected_status not in {"active", "inactive"}:
            selected_status = ""

        medicines_list = (
            Medicine.objects.select_related("medicine_type")
            .prefetch_related("variants")
            .annotate(variant_count=Count("variants", distinct=True))
            .all()
            .order_by("-created_at")
        )
        if selected_type:
            medicines_list = medicines_list.filter(medicine_type_id=selected_type)
        if selected_company:
            medicines_list = medicines_list.filter(company=selected_company)
        if selected_pack == "complete":
            medicines_list = medicines_list.filter(variant_count__gt=0)
        elif selected_pack == "incomplete":
            medicines_list = medicines_list.filter(variant_count=0)
        if selected_stock == "in_stock":
            medicines_list = medicines_list.filter(Exists(
                MedicineVariant.objects.filter(
                    medicine_id=OuterRef("pk"), stock__gt=F("low_stock_alert")
                )
            ))
        elif selected_stock == "low":
            medicines_list = medicines_list.filter(Exists(
                MedicineVariant.objects.filter(
                    medicine_id=OuterRef("pk"),
                    stock__gt=0,
                    stock__lte=F("low_stock_alert"),
                )
            ))
        elif selected_stock == "out":
            variants = MedicineVariant.objects.filter(medicine_id=OuterRef("pk"))
            medicines_list = medicines_list.filter(
                Exists(variants),
                ~Exists(variants.filter(stock__gt=0)),
            )
        if selected_status:
            medicines_list = medicines_list.filter(is_active=(selected_status == "active"))

        paginator = Paginator(medicines_list, 20)
        page_number = request.GET.get("page")
        medicines = paginator.get_page(page_number)
        companies = (
            Medicine.objects.exclude(company="")
            .order_by("company")
            .values_list("company", flat=True)
            .distinct()
        )
        medicine_types = MedicineType.objects.order_by("sort_order", "name")
        type_name = MedicineType.objects.filter(pk=selected_type).values_list("name", flat=True).first() if selected_type else ""
        stock_labels = {"in_stock": "In stock", "low": "Low", "out": "Out"}
        chip_values = [
            ("type", selected_type, "Type: " + type_name),
            ("company", selected_company, "Company: " + selected_company),
            ("pack", selected_pack, "Pack & price: " + selected_pack.title()),
            ("stock", selected_stock, "Stock: " + stock_labels.get(selected_stock, "")),
            ("status", selected_status, "Status: " + selected_status.title()),
        ]
        filter_chips = []
        for key, value, label in chip_values:
            if value:
                params = request.GET.copy()
                params.pop(key, None)
                params.pop("page", None)
                query = params.urlencode()
                filter_chips.append({
                    "label": label,
                    "url": "?" + query if query else request.path,
                })
        pagination_params = request.GET.copy()
        pagination_params.pop("page", None)
        return render(
            request,
            "medicine/manage_medicine.html",
            {
                "medicines": medicines,
                "medicine_types": medicine_types,
                "companies": companies,
                "selected_type": selected_type,
                "selected_company": selected_company,
                "selected_pack": selected_pack,
                "selected_stock": selected_stock,
                "selected_status": selected_status,
                "active_filter_count": len(filter_chips),
                "filter_chips": filter_chips,
                "clear_filters_url": request.path,
                "pagination_query": pagination_params.urlencode(),
            },
        )


class AddMedicineView(LoginRequiredMixin, StaffRequiredMixin, View):
    login_url = "doctor:login"

    def get(self, request):
        medicine_types = MedicineType.objects.filter(is_active=True).order_by("sort_order", "name")
        unit_choices = MedicineVariant.UNIT_CHOICES
        return render(request,"medicine/add_medicine1.html",{"medicine_types": medicine_types,"unit_choices": unit_choices})

    def post(self, request):
        name = request.POST.get("name", "").strip()
        short_name = request.POST.get("short_name", "").strip()
        
        if Medicine.objects.filter(short_name__iexact=short_name).exists():
            messages.error(request, f"A medicine with short name '{short_name}' already exists.")
            return redirect("medicine:add_medicine")

        med_type_id = request.POST.get("medicine_type", "")
        med_type = MedicineType.objects.filter(id=med_type_id).first() if med_type_id else None
        company = request.POST.get("company", "").strip()
        description = request.POST.get("description", "").strip()
        is_active = request.POST.get("is_active") == "on"

        powers = request.POST.getlist("power[]")
        cost_prices = request.POST.getlist("cost_price[]")
        selling_prices = request.POST.getlist("selling_price[]")
        free_samples = request.POST.getlist("free_sample[]")
        price_error = variant_price_error(cost_prices, selling_prices, free_samples, powers)
        if price_error:
            messages.error(request, price_error)
            return redirect("medicine:add_medicine")

        medicine = Medicine.objects.create(
            name=name,
            short_name=short_name,
            medicine_type=med_type,
            company=company,
            description=description,
            is_active=is_active,
        )
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


class DeleteMedicineView(LoginRequiredMixin, StaffRequiredMixin, View):
    login_url = "doctor:login"
    def post(self, request, hid):
        try:
            pk = _hashid.decode_hash(hid)
        except Exception:
            return get_object_or_404(Medicine, id=0)

        medicine = get_object_or_404(Medicine, pk=pk)
        medicine.delete()
        return redirect("medicine:manage_medicine")


class EditMedicineView(LoginRequiredMixin, StaffRequiredMixin, View):
    login_url = "doctor:login"
    def get(self, request, hid):
        try:
            pk = _hashid.decode_hash(hid)
        except Exception:
            return get_object_or_404(Medicine, id=0)

        medicine = get_object_or_404(Medicine.objects.select_related("medicine_type"), pk=pk)
        if medicine.medicine_type_id:
            medicine_types = MedicineType.objects.filter(
                Q(is_active=True) | Q(pk=medicine.medicine_type_id)
            ).distinct().order_by("sort_order", "name")
        else:
            medicine_types = MedicineType.objects.filter(is_active=True).order_by("sort_order", "name")
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
    def post(self, request, hid):
        try:
            pk = _hashid.decode_hash(hid)
        except Exception:
            return get_object_or_404(Medicine, id=0)

        medicine = get_object_or_404(Medicine, pk=pk)
        
        short_name = request.POST.get("short_name", "").strip()
        if Medicine.objects.filter(short_name__iexact=short_name).exclude(pk=medicine.pk).exists():
            messages.error(request, f"A medicine with short name '{short_name}' already exists.")
            return redirect("medicine:edit_medicine", hid=hid)

        med_type_id = request.POST.get("medicine_type", "")
        med_type = MedicineType.objects.filter(id=med_type_id).first() if med_type_id else None

        variant_ids = request.POST.getlist("variant_id[]")
        powers = request.POST.getlist("power[]")
        cost_prices = request.POST.getlist("cost_price[]")
        selling_prices = request.POST.getlist("selling_price[]")
        free_samples = request.POST.getlist("free_sample[]")
        price_error = variant_price_error(cost_prices, selling_prices, free_samples, powers)
        if price_error:
            messages.error(request, price_error)
            return redirect("medicine:edit_medicine", hid=hid)

        medicine.name = request.POST.get("name", "").strip()
        medicine.short_name = short_name
        medicine.medicine_type = med_type
        medicine.company = request.POST.get("company", "").strip()
        medicine.description = request.POST.get("description", "").strip()
        medicine.is_active = request.POST.get("is_active") == "on"
        medicine.save()

        kept_ids = request.POST.getlist("variant_id[]")
        medicine.variants.exclude(pk__in=[i for i in kept_ids if i]).delete()

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


class MedicineSearchView(LoginRequiredMixin, StaffRequiredMixin, View):
    login_url = "doctor:login"

    def get(self, request):
        query = request.GET.get("q", "").strip()

        if len(query) < 2:
            return JsonResponse({"medicines": []})

        medicines = (
            Medicine.objects.select_related("medicine_type")
            .filter(
                Q(name__icontains=query)
                | Q(short_name__icontains=query)
                | Q(company__icontains=query)
                | Q(medicine_type__name__icontains=query)
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
                    "price": str(v.selling_price),  # ← use selling_price
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
                    "type": med.medicine_type.name if med.medicine_type else "—",
                    "company": med.company,
                    "variants": variants,
                }
            )

        return JsonResponse({"medicines": data})


@login_required(login_url="doctor:login")
def search_medicine(request):
    query = request.GET.get("q", "").strip()

    if request.GET.get("grouped") == "1":
        medicine_filter = Q(is_active=True)
        if query:
            medicine_filter &= (
                Q(name__icontains=query)
                | Q(short_name__icontains=query)
                | Q(company__icontains=query)
                | Q(medicine_type__name__icontains=query)
            )
        medicines = (
            Medicine.objects.select_related('medicine_type')
            .prefetch_related('variants')
            .filter(medicine_filter)
            .order_by('name')[:50]
        )
        data = []
        for medicine in medicines:
            variants = [
                {
                    'id': variant.id,
                    'power': variant.power,
                    'price': str(variant.selling_price),
                    'stock': variant.stock,
                    'is_low_stock': variant.is_low_stock,
                    'is_expired': variant.is_expired,
                }
                for variant in medicine.variants.all()
            ]
            data.append({
                'id': medicine.id,
                'name': medicine.name,
                'short_name': medicine.short_name,
                'type': medicine.medicine_type.name if medicine.medicine_type else '—',
                'company': medicine.company,
                'variants': variants,
                'price_not_set': not variants,
            })
        return JsonResponse({'medicines': data})

    if not query:
        variants = (
            MedicineVariant.objects.select_related("medicine", "medicine__medicine_type")
            .filter(medicine__is_active=True)
            .order_by("medicine__name", "power")[:50]
        )
    else:
        variants = (
            MedicineVariant.objects.select_related("medicine", "medicine__medicine_type")
            .filter(
                Q(medicine__name__icontains=query)
                | Q(medicine__short_name__icontains=query)
                | Q(medicine__company__icontains=query)
                | Q(medicine__medicine_type__name__icontains=query),
                medicine__is_active=True,
            )
            .order_by("medicine__name", "power")[:50]
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
                    "type": medicine.medicine_type.name if medicine.medicine_type else "—",
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


class LowStockView(LoginRequiredMixin, StaffRequiredMixin, View):
    login_url = "doctor:login"

    def get(self, request):
        pending_order_items = PurchaseItem.objects.filter(
            medicine_variant=OuterRef("pk"),
            purchase__status="ordered",
        ).order_by("-purchase_id")

        low_stock_variants = (
            MedicineVariant.objects.filter(
                stock__lte=db_models.F("low_stock_alert"),
                medicine__is_active=True
            )
            .annotate(
                is_ordered=Exists(pending_order_items),
                pending_purchase_id=Subquery(
                    pending_order_items.values("purchase_id")[:1]
                ),
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

@login_required(login_url='doctor:login')
def low_stock_count(request):
    if not has_staff_access(request.user):
        return HttpResponseForbidden()
    # Fixed: 'low_stock_alerts' changed to 'low_stock_alert'
    count = MedicineVariant.objects.filter(
        stock__lte=db_models.F("low_stock_alert"), medicine__is_active=True
    ).count()
    return JsonResponse({"count": count})


@login_required(login_url='doctor:login')
def low_stock_list(request):
    if not has_staff_access(request.user):
        return HttpResponseForbidden()
    # Base queryset
    base_query = MedicineVariant.objects.filter(
        stock__lte=db_models.F("low_stock_alert"), medicine__is_active=True
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

    return JsonResponse(
        {"alerts": data, "count": total_count}  # Now returns the true total
    )


class VendorListView(LoginRequiredMixin, StaffRequiredMixin, View):
    login_url = "doctor:login"

    def get(self, request):
        vendors = Vendor.objects.all().order_by("name")
        return render(request, "medicine/vendor_list.html", {"vendors": vendors})


class AddVendorView(LoginRequiredMixin, StaffRequiredMixin, View):
    login_url = "doctor:login"

    def get(self, request):
        return render(request, "medicine/add_vendor.html")

    def post(self, request):
        name = request.POST.get("name", "").strip()
        phone = request.POST.get("phone", "").strip()
        email = request.POST.get("email", "").strip()
        address = request.POST.get("address", "").strip()

        Vendor.objects.create(
            name=name,
            phone=phone,
            email=email,
            address=address,
        )
        messages.success(request, f'Vendor "{name}" added successfully!')
        return redirect("medicine:vendor_list")


class EditVendorView(LoginRequiredMixin, StaffRequiredMixin, View):
    login_url = "doctor:login"
    def get(self, request, hid):
        try:
            pk = _hashid.decode_hash(hid)
        except Exception:
            return get_object_or_404(Vendor, id=0)

        vendor = get_object_or_404(Vendor, pk=pk)
        return render(request, "medicine/edit_vendor.html", {"vendor": vendor})
    def post(self, request, hid):
        try:
            pk = _hashid.decode_hash(hid)
        except Exception:
            return get_object_or_404(Vendor, id=0)

        vendor = get_object_or_404(Vendor, pk=pk)
        vendor.name = request.POST.get("name", "").strip()
        vendor.phone = request.POST.get("phone", "").strip()
        vendor.email = request.POST.get("email", "").strip()
        vendor.address = request.POST.get("address", "").strip()
        vendor.save()

        messages.success(request, f'Vendor "{vendor.name}" updated!')
        return redirect("medicine:vendor_list")


class DeleteVendorView(LoginRequiredMixin, StaffRequiredMixin, View):
    login_url = "doctor:login"
    def post(self, request, hid):
        try:
            pk = _hashid.decode_hash(hid)
        except Exception:
            return get_object_or_404(Vendor, id=0)

        vendor = get_object_or_404(Vendor, pk=pk)
        name = vendor.name
        vendor.delete()
        messages.success(request, f'Vendor "{name}" deleted!')
        return redirect("medicine:vendor_list")


# Purchase Views
class PurchaseListView(LoginRequiredMixin, StaffRequiredMixin, View):
    login_url = "doctor:login"

    def get(self, request):
        search = request.GET.get("search", "").strip()
        purchase_date = request.GET.get("purchase_date", "").strip()
        status = request.GET.get("status", "all").strip()

        purchases = Purchase.objects.select_related("vendor").prefetch_related(
            "items__medicine_variant__medicine"
        )

        if search:
            purchases = purchases.filter(
                Q(vendor__name__icontains=search)
                | Q(items__medicine_variant__medicine__name__icontains=search)
                | Q(items__medicine_variant__medicine__short_name__icontains=search)
                | Q(items__medicine_variant__medicine__company__icontains=search)
            )

        if purchase_date:
            purchases = purchases.filter(date=purchase_date)

        if status and status != "all":
            purchases = purchases.filter(status=status)

        purchases = purchases.distinct().order_by("-date", "-id")
        filtered_purchase_ids = purchases.values("pk")

        stats = Purchase.objects.filter(pk__in=filtered_purchase_ids).aggregate(
            total_spending=db_models.Sum("total_amount"),
            total_purchases=db_models.Count("id"),
        )

        paginator = Paginator(purchases, 20)
        page_number = request.GET.get("page")
        page_obj = paginator.get_page(page_number)

        context = {
            "purchases": page_obj,
            "page_obj": page_obj,
            "search": search,
            "purchase_date": purchase_date,
            "status": status,
            "total_purchases": stats["total_purchases"] or 0,
            "total_spending": stats["total_spending"] or 0,
        }

        return render(request, "medicine/purchase_list.html", context)


class DeletePurchaseView(LoginRequiredMixin, StaffRequiredMixin, View):
    login_url = "doctor:login"
    def post(self, request, hid):
        try:
            pk = _hashid.decode_hash(hid)
        except Exception:
            return get_object_or_404(Purchase, id=0)

        purchase = get_object_or_404(Purchase, pk=pk)
        purchase.delete()
        messages.success(request, "Purchase deleted successfully.")
        return redirect("medicine:purchase_list")


class AddPurchaseView(LoginRequiredMixin, StaffRequiredMixin, View):
    login_url = "doctor:login"

    def get(self, request):

        vendors = Vendor.objects.all().order_by("name")

        preselected_variant = None
        variant_id = request.GET.get("variant")

        if variant_id:
            try:
                preselected_variant = MedicineVariant.objects.select_related(
                    "medicine"
                ).get(pk=variant_id)

            except MedicineVariant.DoesNotExist:
                pass

            else:
                pending_purchase = (
                    Purchase.objects.filter(
                        items__medicine_variant=preselected_variant,status="ordered",
                    ).order_by("-id").first()
                )

                if pending_purchase:
                    messages.warning(
                        request,
                        f"{preselected_variant.medicine.name} already has a pending order.",
                    )

                    return redirect("medicine:purchase_detail",hid=_hashid.encode_id(pending_purchase.pk))

        return render(request,"medicine/add_purchase.html",{
                "vendors": vendors,
                "preselected_variant": preselected_variant,
            },
        )

    def post(self, request):

        vendor_id = request.POST.get("vendor")
        vendor = get_object_or_404(Vendor, pk=vendor_id)

        variant_ids = request.POST.getlist("variant_id[]")
        qty_strips_list = request.POST.getlist("quantity_strips[]")
        ups_list = request.POST.getlist("unit_per_strip[]")

        strip_price_list = request.POST.getlist("strip_price[]")
        tax_list = request.POST.getlist("tax_percent[]")
        discount_list = request.POST.getlist("discount_amount[]")

        # Validation
        if not any(variant_ids):
            messages.error(request, "Please add at least one medicine!")
            return redirect("medicine:add_purchase")

        selected_variant_ids = [v_id for v_id in variant_ids if v_id]

        if len(selected_variant_ids) != len(set(selected_variant_ids)):
            messages.error(
                request,
                "Please add each medicine only once in a purchase.",
            )
            return redirect("medicine:add_purchase")

        # Pending validation
        pending_item = (
            PurchaseItem.objects.select_related("purchase","medicine_variant__medicine",)
            .filter(medicine_variant_id__in=selected_variant_ids,purchase__status="ordered",)
            .first()
        )

        if pending_item:

            medicine_name = pending_item.medicine_variant.medicine.name

            messages.error(request,f"{medicine_name} already has a pending purchase order.",)

            return redirect("medicine:purchase_detail",hid=_hashid.encode_id(pending_item.purchase_id),)

        # Purchase Create
        purchase = Purchase.objects.create(
            vendor=vendor,
            total_amount=0,
            status="ordered",
        )

        grand_total = Decimal("0.00")

        for (
            v_id,
            qty_str,
            ups_str,
            strip_price_str,
            tax_str,
            discount_str,
        ) in zip(
            variant_ids,
            qty_strips_list,
            ups_list,
            strip_price_list,
            tax_list,
            discount_list,
        ):

            if not v_id:
                continue

            variant = get_object_or_404(MedicineVariant,pk=v_id,)

            # Convert values
            qty_strips = int(qty_str or 0)
            unit_per_strip = int(ups_str or 1)

            strip_price = Decimal(strip_price_str or "0")
            tax_percent = Decimal(tax_str or "0")
            discount_amount = Decimal(discount_str or "0")

            # Total units
            total_units = qty_strips * unit_per_strip

            # Price calculations
            subtotal = Decimal(qty_strips) * strip_price

            tax_amount = (
                subtotal * tax_percent
            ) / Decimal("100")

            final_amount = (subtotal + tax_amount - discount_amount)

            effective_unit_cost = (final_amount / total_units if total_units > 0 else Decimal("0"))

            # Save Purchase Item
            PurchaseItem.objects.create(
                purchase=purchase,
                medicine_variant=variant,

                quantity_strips=qty_strips,
                unit_per_strip=unit_per_strip,

                strip_price=strip_price,
                tax_percent=tax_percent,
                discount_amount=discount_amount,

                total_units=total_units,
                final_amount=final_amount,
                effective_unit_cost=effective_unit_cost,
            )

            grand_total += final_amount

        purchase.total_amount = grand_total
        purchase.save()

        messages.success(request,f"Purchase order created successfully. Total ₹{grand_total}",)
        return redirect("medicine:purchase_list")

class ReceivePurchaseView(LoginRequiredMixin, StaffRequiredMixin, View):
    login_url = "doctor:login"

    def get(self, request, hid):
        try:
            pk = _hashid.decode_hash(hid)
        except Exception:
            return get_object_or_404(Purchase, id=0)

        purchase = get_object_or_404(
            Purchase.objects.select_related("vendor").prefetch_related("items__medicine_variant__medicine")
            ,pk=pk,)

        # Already received validation
        if purchase.status == "received":
            messages.warning(request, "Purchase already received.")
            return redirect("medicine:purchase_detail", hid=_hashid.encode_id(pk))

        context = {"purchase": purchase,}

        return render(request,"medicine/receive_purchase.html",context,)

    def post(self, request, hid):
        try:
            pk = _hashid.decode_hash(hid)
        except Exception:
            return get_object_or_404(Purchase, id=0)

        purchase = get_object_or_404(Purchase.objects.prefetch_related("items__medicine_variant"),pk=pk,)

        # Prevent duplicate receive
        if purchase.status == "received":
            messages.warning(request, "Purchase already received.")
            return redirect("medicine:purchase_detail", hid=_hashid.encode_id(pk))

        item_ids = request.POST.getlist("item_id[]")
        received_qty_list = request.POST.getlist("received_quantity_strips[]")
        strip_price_list = request.POST.getlist("strip_price[]")
        tax_list = request.POST.getlist("tax_percent[]")
        discount_list = request.POST.getlist("discount_amount[]")
        mfg_date_list = request.POST.getlist("mfg_date[]")
        exp_date_list = request.POST.getlist("exp_date[]")

        from django.db import transaction
        grand_total = Decimal("0.00")

        with transaction.atomic():
            for (
                item_id,
                received_qty_str,
                strip_price_str,
                tax_str,
                discount_str,
                mfg_date_str,
                exp_date_str,
            ) in zip(item_ids,received_qty_list,strip_price_list,tax_list,discount_list,
            mfg_date_list,exp_date_list,):

                purchase_item = get_object_or_404(PurchaseItem,pk=item_id,purchase=purchase,)
    
                # Lock the variant to prevent race conditions when updating stock
                variant = MedicineVariant.objects.select_for_update().get(pk=purchase_item.medicine_variant_id)
    
                # Convert values
                received_qty = int(received_qty_str or 0)
                strip_price = Decimal(strip_price_str or "0")
                tax_percent = Decimal(tax_str or "0")
                discount_amount = Decimal(discount_str or "0")
    
                # Total units
                total_units = (
                    received_qty *
                    purchase_item.unit_per_strip
                )
    
                # Price calculations
                subtotal = (
                    Decimal(received_qty) *
                    strip_price
                )
    
                tax_amount = (
                    subtotal * tax_percent
                ) / Decimal("100")
    
                final_amount = (
                    subtotal +
                    tax_amount -
                    discount_amount
                )
    
                effective_unit_cost = (
                    final_amount / total_units
                    if total_units > 0
                    else Decimal("0")
                )
    
                # Save receive details
                purchase_item.received_quantity_strips = received_qty
                purchase_item.strip_price = strip_price
                purchase_item.tax_percent = tax_percent
                purchase_item.discount_amount = discount_amount
                purchase_item.total_units = total_units
                purchase_item.final_amount = final_amount
                purchase_item.effective_unit_cost = (
                    effective_unit_cost
                )
                purchase_item.is_received = True
                purchase_item.save()
    
                # Stock update
                variant.stock += total_units
    
                # Initial costing
                variant.cost_price = effective_unit_cost
                variant.unit_per_strip = (
                    purchase_item.unit_per_strip
                )
                
                if mfg_date_str:
                    variant.mfg_date = mfg_date_str
                if exp_date_str:
                    variant.exp_date = exp_date_str
    
                variant.save()
    
                grand_total += final_amount
    
            # Purchase update
            purchase.total_amount = grand_total
            purchase.status = "received"
            purchase.save()

        messages.success(request,"Purchase received successfully.")

        return redirect("medicine:purchase_detail", hid=_hashid.encode_id(purchase.pk))

class PurchaseDetailView(LoginRequiredMixin, StaffRequiredMixin, View):
    login_url = "doctor:login"
    def get(self, request, hid):
        try:
            pk = _hashid.decode_hash(hid)
        except Exception:
            return get_object_or_404(Purchase, id=0)

        purchase = get_object_or_404(
            Purchase.objects.select_related("vendor").prefetch_related("items__medicine_variant__medicine"),
            pk=pk,
        )
        return render(request, "medicine/purchase_detail.html", {"purchase": purchase})

# Medicine Import 
class ImportMedicineView(LoginRequiredMixin, StaffRequiredMixin, View):
    login_url = "doctor:login"
    MAX_UPLOAD_SIZE = 5 * 1024 * 1024
    STOCK_OPTIONS = {'add', 'replace', 'keep'}
    IMPORT_TYPES = {'full', 'names_only'}

    def _summary(self, rows):
        return {
            'total': len(rows),
            'new_medicine': sum(row.get('status') == 'New medicine' for row in rows),
            'new_variant': sum(row.get('status') == 'New variant' for row in rows),
            'update': sum(row.get('status') == 'Update existing' for row in rows),
            'error': sum(row.get('status') == 'Error' for row in rows),
            'importable': sum(row.get('status') != 'Error' for row in rows),
        }

    def _render_preview(self, request, rows=None, error=None):
        preview = request.session.get('medicine_import_preview', {})
        rows = rows if rows is not None else preview.get('rows', [])
        last_import = request.session.get('medicine_last_import', {})
        import_type = preview.get('import_type', 'full')
        show_duplicate_warning = (
            import_type == 'full'
            and
            preview.get('stock_option') == 'add'
            and bool(preview.get('file_hash'))
            and preview.get('file_hash') == last_import.get('file_hash')
        )
        if error:
            messages.error(request, error)
        summary = self._summary(rows)
        sheet_counts = []
        if import_type == 'names_only':
            summary.update({
                'new': sum(row.get('status') == 'New' for row in rows),
                'already_exists': sum(row.get('status') == 'Already exists' for row in rows),
                'error': sum(row.get('status') == 'Error' for row in rows),
                'importable': sum(row.get('status') == 'New' for row in rows),
            })
            by_sheet = {}
            for row in rows:
                sheet_name = row.get('sheet_name', '')
                counts = by_sheet.setdefault(sheet_name, {'sheet_name': sheet_name, 'total': 0, 'new': 0, 'already_exists': 0, 'error': 0})
                counts['total'] += 1
                if row.get('status') == 'New':
                    counts['new'] += 1
                elif row.get('status') == 'Already exists':
                    counts['already_exists'] += 1
                elif row.get('status') == 'Error':
                    counts['error'] += 1
            sheet_counts = list(by_sheet.values())

        return render(request, 'medicine/import_medicine.html', {
            'step': 'preview',
            'preview_rows': rows,
            'summary': summary,
            'import_type': import_type,
            'sheet_counts': sheet_counts,
            'stock_option': preview.get('stock_option', 'add'),
            'stock_option_label': {
                'add': 'Add to existing stock',
                'replace': 'Replace existing stock',
                'keep': "Don't change stock of existing variants",
            }.get(preview.get('stock_option'), 'Add to existing stock'),
            'duplicate_import_warning': show_duplicate_warning,
            'last_import_date': last_import.get('date', ''),
        })

    def get(self, request):
        if request.GET.get('download_sample') == '1':
            response = HttpResponse(
                generate_sample_excel(),
                content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            )
            response['Content-Disposition'] = 'attachment; filename="medicine_import_sample.xlsx"'
            return response
        if request.GET.get('download_errors') == '1':
            error_rows = request.session.get('medicine_import_errors', [])
            response = HttpResponse(
                generate_error_excel(error_rows),
                content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            )
            response['Content-Disposition'] = 'attachment; filename="medicine_import_errors.xlsx"'
            return response
        request.session.pop('medicine_import_preview', None)
        return render(request, 'medicine/import_medicine.html', {'step': 'upload'})

    def post(self, request):
        action = request.POST.get('action', 'upload')
        if action == 'cancel':
            request.session.pop('medicine_import_preview', None)
            return render(request, 'medicine/import_medicine.html', {'step': 'upload'})

        if action == 'upload':
            request.session.pop('medicine_import_preview', None)
            import_type = request.POST.get('import_type', 'full')
            stock_option = request.POST.get('stock_option', '')
            excel_file = request.FILES.get('excel_file')
            if import_type not in self.IMPORT_TYPES:
                messages.error(request, 'Select a valid import type.')
                return render(request, 'medicine/import_medicine.html', {'step': 'upload'})
            if import_type == 'full' and stock_option not in self.STOCK_OPTIONS:
                messages.error(request, 'Select a stock option before uploading.')
                return render(request, 'medicine/import_medicine.html', {'step': 'upload'})
            if not excel_file:
                messages.error(request, 'Please upload an Excel file.')
                return render(request, 'medicine/import_medicine.html', {'step': 'upload'})
            if not excel_file.name.lower().endswith('.xlsx'):
                messages.error(request, 'Only .xlsx files are supported.')
                return render(request, 'medicine/import_medicine.html', {'step': 'upload'})
            if excel_file.size > self.MAX_UPLOAD_SIZE:
                messages.error(request, 'The Excel file must be 5 MB or smaller.')
                return render(request, 'medicine/import_medicine.html', {'step': 'upload'})

            content = excel_file.read()
            file_hash = hashlib.sha256(content).hexdigest()
            try:
                rows = (
                    parse_names_only_excel(BytesIO(content))
                    if import_type == 'names_only'
                    else parse_medicine_excel(BytesIO(content))
                )
            except MissingRequiredHeaders as exc:
                messages.error(request, str(exc))
                return render(request, 'medicine/import_medicine.html', {'step': 'upload'})
            except Exception as exc:
                messages.error(request, f'Could not read the Excel file: {exc}')
                return render(request, 'medicine/import_medicine.html', {'step': 'upload'})

            if not rows:
                messages.error(request, 'The uploaded workbook contains no data rows.')
                return render(request, 'medicine/import_medicine.html', {'step': 'upload'})
            request.session['medicine_import_preview'] = {
                'rows': rows,
                'file_hash': file_hash,
                'stock_option': stock_option,
                'import_type': import_type,
            }
            return self._render_preview(request, rows)

        if action == 'import':
            preview = request.session.get('medicine_import_preview')
            if not preview or not preview.get('rows'):
                messages.error(request, 'No preview is available. Upload the file again.')
                return render(request, 'medicine/import_medicine.html', {'step': 'upload'})

            last_import = request.session.get('medicine_last_import', {})
            is_duplicate_add = (
                preview.get('import_type', 'full') == 'full'
                and
                preview.get('stock_option') == 'add'
                and preview.get('file_hash') == last_import.get('file_hash')
            )
            if is_duplicate_add and request.POST.get('confirm_duplicate') != 'on':
                return self._render_preview(
                    request,
                    error='Confirm that you want to add this file to existing stock again.',
                )

            if preview.get('import_type') == 'names_only':
                result = import_names_only_rows(preview['rows'])
            else:
                result = import_medicine_rows(preview['rows'], preview.get('stock_option', 'add'))
            request.session['medicine_import_errors'] = result['error_rows']
            imported_at = timezone.localtime()
            request.session['medicine_last_import'] = {
                'file_hash': preview.get('file_hash'),
                'date': imported_at.strftime('%d %b %Y %H:%M'),
            }
            summary = {
                'total': result['total'],
                'imported': result['success_count'],
                'error': len(result['error_rows']),
                'already_exists': sum(row.get('status') == 'Already exists' for row in preview['rows']),
            }
            request.session.pop('medicine_import_preview', None)
            return render(request, 'medicine/import_medicine.html', {
                'step': 'done',
                'summary': summary,
            })

        messages.error(request, 'Invalid import action. Start again by uploading the workbook.')
        return render(request, 'medicine/import_medicine.html', {'step': 'upload'})


class MedicineTypeListView(LoginRequiredMixin, StaffRequiredMixin, View):
    login_url = "doctor:login"

    def get(self, request):
        types = (
            MedicineType.objects.annotate(medicine_count=Count("medicines"))
            .order_by("sort_order", "name")
        )
        return render(request, "medicine/medicine_types.html", {"types": types})

    def post(self, request):
        name = request.POST.get("name", "").strip()
        sort_order_raw = request.POST.get("sort_order", "0").strip()
        is_active = (
            request.POST.get("is_active") == "on"
            or request.POST.get("is_active") == "true"
            or request.POST.get("is_active") == "1"
        )

        if not name:
            messages.error(request, "Medicine type name is required.")
            return redirect("medicine:medicine_types")

        if MedicineType.objects.filter(name__iexact=name).exists():
            messages.error(request, f"Medicine type '{name}' already exists.")
            return redirect("medicine:medicine_types")

        try:
            sort_order = int(sort_order_raw)
        except (ValueError, TypeError):
            sort_order = 0

        MedicineType.objects.create(
            name=name,
            sort_order=sort_order,
            is_active=is_active,
        )
        messages.success(request, f'Medicine type "{name}" added successfully.')
        return redirect("medicine:medicine_types")


class EditMedicineTypeView(LoginRequiredMixin, StaffRequiredMixin, View):
    login_url = "doctor:login"

    def get(self, request, pk):
        med_type = get_object_or_404(MedicineType, pk=pk)
        return render(request, "medicine/edit_medicine_type.html", {"med_type": med_type})

    def post(self, request, pk):
        med_type = get_object_or_404(MedicineType, pk=pk)
        name = request.POST.get("name", "").strip()
        sort_order_raw = request.POST.get("sort_order", "0").strip()
        is_active = (
            request.POST.get("is_active") == "on"
            or request.POST.get("is_active") == "true"
            or request.POST.get("is_active") == "1"
        )

        if not name:
            messages.error(request, "Medicine type name is required.")
            return redirect("medicine:edit_medicine_type", pk=pk)

        if MedicineType.objects.filter(name__iexact=name).exclude(pk=pk).exists():
            messages.error(request, f"Medicine type '{name}' already exists.")
            return redirect("medicine:edit_medicine_type", pk=pk)

        try:
            sort_order = int(sort_order_raw)
        except (ValueError, TypeError):
            sort_order = 0

        med_type.name = name
        med_type.sort_order = sort_order
        med_type.is_active = is_active
        med_type.save()

        messages.success(request, f'Medicine type "{name}" updated successfully.')
        return redirect("medicine:medicine_types")


class DeleteMedicineTypeView(LoginRequiredMixin, StaffRequiredMixin, View):
    login_url = "doctor:login"

    def get(self, request, pk):
        return HttpResponseNotAllowed(["POST"])

    def post(self, request, pk):
        med_type = get_object_or_404(MedicineType, pk=pk)
        med_count = med_type.medicines.count()

        if med_count > 0:
            messages.error(
                request,
                f"This type is used by {med_count} medicines. Deactivate it instead.",
            )
            return redirect("medicine:medicine_types")

        name = med_type.name
        med_type.delete()
        messages.success(request, f'Medicine type "{name}" deleted successfully.')
        return redirect("medicine:medicine_types")
