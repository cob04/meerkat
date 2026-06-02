from django.shortcuts import render
from django.urls import reverse_lazy

from apps.core.services import dashboard_snapshot
from apps.search.contracts import DEFAULT_LOW_STOCK_THRESHOLD

PRIORITY_QUESTIONS = [
    {
        "num": "01",
        "text": "Find any item, batch, or product across the network",
        "cta": "Search catalog",
        "url": reverse_lazy("search:catalog-search"),
    },
    {
        "num": "02",
        "text": "Where is a product in stock, and how far away?",
        "cta": "Check availability",
        "url": reverse_lazy("search:availability"),
    },
    {
        "num": "03",
        "text": "Which batches are expiring soon?",
        "cta": "Open expiry",
        "url": reverse_lazy("search:expiry"),
    },
    {
        "num": "04",
        "text": "What is running low and needs reorder?",
        "cta": "View low stock",
        "url": reverse_lazy("search:low-stock"),
    },
    {
        "num": "05",
        "text": "Which items are affected by a recall?",
        "cta": "Recall lookup",
        "url": reverse_lazy("search:recall-lookup"),
    },
]


def dashboard(request):
    context = {
        "snapshot": dashboard_snapshot(),
        "questions": PRIORITY_QUESTIONS,
        "low_stock_threshold": DEFAULT_LOW_STOCK_THRESHOLD,
    }
    return render(request, "core/dashboard.html", context)
