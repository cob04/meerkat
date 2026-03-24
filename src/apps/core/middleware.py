import threading

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
