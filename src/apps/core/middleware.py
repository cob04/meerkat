import json
import threading

from django.contrib.messages import get_messages
from django.utils.deprecation import MiddlewareMixin

_thread_local = threading.local()


def get_current_user():
    user = getattr(_thread_local, "user", None)
    if user and user.is_authenticated:
        return user
    return None


class CurrentUserMiddleware(MiddlewareMixin):
    def process_request(self, request):
        _thread_local.user = getattr(request, "user", None)

    def process_response(self, request, response):
        _thread_local.user = None
        return response


class HtmxMessagesMiddleware(MiddlewareMixin):
    """Drain pending Django messages into HX-Trigger showToast events on HTMX responses."""

    def process_response(self, request, response):
        if request.headers.get("HX-Request") != "true":
            return response
        if not hasattr(request, "_messages"):
            return response

        toasts = [
            {"message": str(message), "kind": _kind_for(message.level_tag)}
            for message in get_messages(request)
        ]
        if not toasts:
            return response

        triggers = _existing_triggers(response)
        triggers["showToast"] = toasts
        response["HX-Trigger"] = json.dumps(triggers)
        return response


_KIND_MAP = {
    "debug": "info",
    "info": "info",
    "success": "success",
    "warning": "warning",
    "error": "error",
}


def _kind_for(level_tag: str) -> str:
    return _KIND_MAP.get(level_tag, "info")


def _existing_triggers(response) -> dict:
    raw = response.get("HX-Trigger")
    if not raw:
        return {}
    try:
        loaded = json.loads(raw)
    except json.JSONDecodeError:
        return {raw: True}
    return loaded if isinstance(loaded, dict) else {}
