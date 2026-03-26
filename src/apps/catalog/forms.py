from django import forms

from apps.catalog.models import InventoryItem, Location, Product

FIELD_CSS = (
    "flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm "
    "shadow-xs transition-colors placeholder:text-muted-foreground "
    "focus:outline-none focus:ring-1 focus:ring-ring"
)
SELECT_CSS = FIELD_CSS
TEXTAREA_CSS = (
    "flex w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm "
    "shadow-xs transition-colors placeholder:text-muted-foreground "
    "focus:outline-none focus:ring-1 focus:ring-ring resize-y"
)


class TailwindFormMixin:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            widget = field.widget
            if isinstance(widget, forms.Textarea):
                widget.attrs.setdefault("class", TEXTAREA_CSS)
                widget.attrs.setdefault("rows", 2)
            elif isinstance(widget, forms.Select):
                widget.attrs.setdefault("class", SELECT_CSS)
            elif isinstance(widget, (forms.TextInput, forms.NumberInput, forms.DateInput)):
                widget.attrs.setdefault("class", FIELD_CSS)


class ReceiveStockForm(TailwindFormMixin, forms.Form):
    item_name = forms.CharField(max_length=255)
    product = forms.ModelChoiceField(
        queryset=Product.objects.filter(is_active=True),
        required=False,
        empty_label="-- No product --",
    )
    location = forms.ModelChoiceField(
        queryset=Location.objects.all(), empty_label="Select a location"
    )
    batch_number = forms.CharField(max_length=100)
    quantity = forms.IntegerField(min_value=1)
    expiry_date = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))
    unit_cost = forms.DecimalField(max_digits=10, decimal_places=2, min_value=0)
    notes = forms.CharField(widget=forms.Textarea, required=False)


class DispenseStockForm(TailwindFormMixin, forms.Form):
    quantity = forms.IntegerField(min_value=1)
    notes = forms.CharField(widget=forms.Textarea, required=False)


class TransferStockForm(TailwindFormMixin, forms.Form):
    to_location = forms.ModelChoiceField(
        queryset=Location.objects.all(), empty_label="Select a location"
    )
    quantity = forms.IntegerField(min_value=1)
    notes = forms.CharField(widget=forms.Textarea, required=False)

    def __init__(self, *args, exclude_location=None, **kwargs):
        super().__init__(*args, **kwargs)
        if exclude_location:
            self.fields["to_location"].queryset = Location.objects.exclude(pk=exclude_location.pk)


class AdjustStockForm(TailwindFormMixin, forms.Form):
    new_quantity = forms.IntegerField(min_value=0)
    reason = forms.CharField(widget=forms.Textarea)


class ReturnStockForm(TailwindFormMixin, forms.Form):
    quantity = forms.IntegerField(min_value=1)
    notes = forms.CharField(widget=forms.Textarea, required=False)


class RecallBatchForm(TailwindFormMixin, forms.Form):
    batch_number = forms.CharField(max_length=100)
    reason = forms.CharField(widget=forms.Textarea)


class InventoryFilterForm(TailwindFormMixin, forms.Form):
    search = forms.CharField(
        required=False, widget=forms.TextInput(attrs={"placeholder": "Search..."})
    )
    status = forms.ChoiceField(
        choices=[("", "All statuses")] + list(InventoryItem.Status.choices),
        required=False,
    )
    location = forms.ModelChoiceField(
        queryset=Location.objects.all(),
        required=False,
        empty_label="All locations",
    )
