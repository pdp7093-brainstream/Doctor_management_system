from django.shortcuts import render, redirect, get_object_or_404
from doctor import hashid as _hashid
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.db.models import Q, Exists, OuterRef, Subquery
from .models import *
from django.core.paginator import Paginator
from django.db import models as db_models
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from decimal import Decimal
from .services.medicine_importer import import_medicines_from_excel

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
        return render(request,"medicine/add_medicine1.html",{"medicine_types": medicine_types,"unit_choices": unit_choices})

    def post(self, request):
        name = request.POST.get("name", "").strip()
        short_name = request.POST.get("short_name", "").strip()
        
        if Medicine.objects.filter(short_name__iexact=short_name).exists():
            messages.error(request, f"A medicine with short name '{short_name}' already exists.")
            return redirect("medicine:add_medicine")

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
    def post(self, request, hid):
        try:
            pk = _hashid.decode_hash(hid)
        except Exception:
            return get_object_or_404(Medicine, id=0)

        medicine = get_object_or_404(Medicine, pk=pk)
        medicine.delete()
        return redirect("medicine:manage_medicine")


class EditMedicineView(LoginRequiredMixin, View):
    login_url = "doctor:login"
    def get(self, request, hid):
        try:
            pk = _hashid.decode_hash(hid)
        except Exception:
            return get_object_or_404(Medicine, id=0)

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

        medicine.name = request.POST.get("name", "").strip()
        medicine.short_name = short_name
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
        variants = (
            MedicineVariant.objects.select_related("medicine")
            .filter(medicine__is_active=True)
            .order_by("medicine__name", "power")[:50]
        )
    else:
        variants = (
            MedicineVariant.objects.select_related("medicine")
            .filter(
                Q(medicine__name__icontains=query)
                | Q(medicine__short_name__icontains=query)
                | Q(medicine__company__icontains=query),
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

def low_stock_count(request):
    # Fixed: 'low_stock_alerts' changed to 'low_stock_alert'
    count = MedicineVariant.objects.filter(
        stock__lte=db_models.F("low_stock_alert"), medicine__is_active=True
    ).count()
    return JsonResponse({"count": count})


def low_stock_list(request):
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


class VendorListView(LoginRequiredMixin, View):
    login_url = "doctor:login"

    def get(self, request):
        vendors = Vendor.objects.all().order_by("name")
        return render(request, "medicine/vendor_list.html", {"vendors": vendors})


class AddVendorView(LoginRequiredMixin, View):
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


class EditVendorView(LoginRequiredMixin, View):
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


class DeleteVendorView(LoginRequiredMixin, View):
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
class PurchaseListView(LoginRequiredMixin, View):
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


class DeletePurchaseView(LoginRequiredMixin, View):
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


class AddPurchaseView(LoginRequiredMixin, View):
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

class ReceivePurchaseView(LoginRequiredMixin, View):
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

class PurchaseDetailView(LoginRequiredMixin, View):
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
class ImportMedicineView(LoginRequiredMixin, View):
    login_url = "doctor:login"

    def get(self,request):
        return render(request,"medicine/import_medicine.html")
    
    def post(self,request):
        excel_file = request.FILES.get("excel_file")

        if not excel_file:
            messages.error(request,"Please upload an Excel file.")
            return redirect("medicine:import_medicine")

        try:
            result = import_medicines_from_excel(excel_file)

            messages.success(
                request,f"{result['success_count']} medicines imported successfully"
            )

            if result["errors"]:
                for error in result["errors"]:
                    messages.warning(request,error)

        except Exception as e:
            messages.error(request, f"Import failed: {str(e)}")
        
        return redirect("medicine:manage_medicine")
        