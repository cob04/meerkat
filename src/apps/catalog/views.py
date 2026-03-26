from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from apps.catalog import services
from apps.catalog.forms import (
    AdjustStockForm,
    DispenseStockForm,
    InventoryFilterForm,
    RecallBatchForm,
    ReceiveStockForm,
    ReturnStockForm,
    TransferStockForm,
)
from apps.catalog.models import InventoryItem, Location, Product


def _render(request, full_template: str, partial_template: str, context: dict):
    template = partial_template if request.headers.get("HX-Request") else full_template
    return render(request, template, context)


def inventory_list(request):
    filter_form = InventoryFilterForm(request.GET)
    qs = InventoryItem.objects.select_related("product", "location")

    if filter_form.is_valid():
        search = filter_form.cleaned_data.get("search")
        status = filter_form.cleaned_data.get("status")
        location = filter_form.cleaned_data.get("location")

        if search:
            qs = qs.filter(
                Q(item_name__icontains=search)
                | Q(batch_number__icontains=search)
                | Q(product__name__icontains=search)
            )
        if status:
            qs = qs.filter(status=status)
        if location:
            qs = qs.filter(location=location)

    paginator = Paginator(qs, 25)
    page = paginator.get_page(request.GET.get("page"))
    context = {"page": page, "filter_form": filter_form}
    return _render(
        request,
        "catalog/inventory/list.html",
        "catalog/inventory/_list_table.html",
        context,
    )


def inventory_detail(request, pk):
    item = get_object_or_404(
        InventoryItem.objects.select_related("product", "location"),
        pk=pk,
    )
    movements = item.movements.select_related(
        "from_location", "to_location", "performed_by"
    ).order_by("-created_at")[:20]
    return render(
        request,
        "catalog/inventory/detail.html",
        {"item": item, "movements": movements},
    )


def receive_stock_view(request):
    if request.method == "POST":
        form = ReceiveStockForm(request.POST)
        if form.is_valid():
            data = form.cleaned_data
            item = services.receive_stock(
                item_name=data["item_name"],
                location=data["location"],
                batch_number=data["batch_number"],
                quantity=data["quantity"],
                expiry_date=data["expiry_date"],
                unit_cost=data["unit_cost"],
                user=request.user,
                product=data.get("product"),
                notes=data.get("notes", ""),
            )
            messages.success(request, f"Received {data['quantity']}x {data['item_name']}.")
            return redirect("catalog:inventory-detail", pk=item.pk)
    else:
        form = ReceiveStockForm()
    return render(request, "catalog/inventory/receive_form.html", {"form": form})


def dispense_stock_view(request, pk):
    item = get_object_or_404(InventoryItem.objects.select_related("location"), pk=pk)
    if request.method == "POST":
        form = DispenseStockForm(request.POST)
        if form.is_valid():
            try:
                services.dispense_stock(
                    item=item,
                    quantity=form.cleaned_data["quantity"],
                    user=request.user,
                    notes=form.cleaned_data.get("notes", ""),
                )
                messages.success(
                    request, f"Dispensed {form.cleaned_data['quantity']}x {item.item_name}."
                )
                return redirect("catalog:inventory-detail", pk=item.pk)
            except ValueError as e:
                form.add_error(None, str(e))
    else:
        form = DispenseStockForm()
    return render(request, "catalog/inventory/dispense_form.html", {"form": form, "item": item})


def transfer_stock_view(request, pk):
    item = get_object_or_404(InventoryItem.objects.select_related("location"), pk=pk)
    if request.method == "POST":
        form = TransferStockForm(request.POST, exclude_location=item.location)
        if form.is_valid():
            try:
                services.transfer_stock(
                    item=item,
                    to_location=form.cleaned_data["to_location"],
                    quantity=form.cleaned_data["quantity"],
                    user=request.user,
                    notes=form.cleaned_data.get("notes", ""),
                )
                messages.success(
                    request, f"Transferred {form.cleaned_data['quantity']}x {item.item_name}."
                )
                return redirect("catalog:inventory-detail", pk=item.pk)
            except ValueError as e:
                form.add_error(None, str(e))
    else:
        form = TransferStockForm(exclude_location=item.location)
    return render(request, "catalog/inventory/transfer_form.html", {"form": form, "item": item})


def adjust_stock_view(request, pk):
    item = get_object_or_404(InventoryItem.objects.select_related("location"), pk=pk)
    if request.method == "POST":
        form = AdjustStockForm(request.POST)
        if form.is_valid():
            try:
                services.adjust_stock(
                    item=item,
                    new_quantity=form.cleaned_data["new_quantity"],
                    reason=form.cleaned_data["reason"],
                    user=request.user,
                )
                messages.success(request, f"Adjusted {item.item_name} stock.")
                return redirect("catalog:inventory-detail", pk=item.pk)
            except ValueError as e:
                form.add_error(None, str(e))
    else:
        form = AdjustStockForm(initial={"new_quantity": item.quantity})
    return render(request, "catalog/inventory/adjust_form.html", {"form": form, "item": item})


def return_stock_view(request, pk):
    item = get_object_or_404(InventoryItem.objects.select_related("location"), pk=pk)
    if request.method == "POST":
        form = ReturnStockForm(request.POST)
        if form.is_valid():
            try:
                services.return_stock(
                    item=item,
                    quantity=form.cleaned_data["quantity"],
                    user=request.user,
                    notes=form.cleaned_data.get("notes", ""),
                )
                messages.success(
                    request, f"Returned {form.cleaned_data['quantity']}x {item.item_name}."
                )
                return redirect("catalog:inventory-detail", pk=item.pk)
            except ValueError as e:
                form.add_error(None, str(e))
    else:
        form = ReturnStockForm()
    return render(request, "catalog/inventory/return_form.html", {"form": form, "item": item})


def recall_batch_view(request):
    if request.method == "POST":
        form = RecallBatchForm(request.POST)
        if form.is_valid():
            try:
                items = services.recall_batch(
                    batch_number=form.cleaned_data["batch_number"],
                    reason=form.cleaned_data["reason"],
                    user=request.user,
                )
                messages.success(
                    request,
                    f"Recalled {len(items)} item(s) from batch {form.cleaned_data['batch_number']}.",
                )
                return redirect("catalog:inventory-list")
            except ValueError as e:
                form.add_error(None, str(e))
    else:
        form = RecallBatchForm()
    return render(request, "catalog/inventory/recall_form.html", {"form": form})


def location_list(request):
    locations = Location.objects.all()
    return render(request, "catalog/locations/list.html", {"locations": locations})


def product_list(request):
    products = Product.objects.select_related("drug").all()
    return render(request, "catalog/products/list.html", {"products": products})
