from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path


def health(request):
    return JsonResponse({"status": "ok"})


urlpatterns = [
    path("admin/", admin.site.urls),
    path("health/", health),
    path("search/", include("apps.search.urls")),
    path("", include("apps.core.urls")),
    path("", include("apps.catalog.urls")),
]
