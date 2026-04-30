import json

import pytest
from django.contrib import messages
from django.http import HttpResponse
from django.test import RequestFactory, override_settings

from apps.core.middleware import HtmxMessagesMiddleware


@pytest.fixture
def factory():
    return RequestFactory()


def _request_with_messages(factory, htmx=False, level_pairs=()):
    headers = {"HTTP_HX_REQUEST": "true"} if htmx else {}
    request = factory.get("/", **headers)
    setattr(request, "session", {})
    setattr(request, "_messages", _FakeMessageStorage())
    for level, message in level_pairs:
        request._messages.add(level, message)
    return request


class _FakeMessageStorage:
    def __init__(self):
        self._items = []

    def add(self, level, msg):
        self._items.append(_FakeMessage(level, msg))

    def __iter__(self):
        for item in self._items:
            item.used = True
            yield item


class _FakeMessage:
    def __init__(self, level, message):
        self.level = level
        self.message = message
        self.used = False
        self.level_tag = {
            messages.DEBUG: "debug",
            messages.INFO: "info",
            messages.SUCCESS: "success",
            messages.WARNING: "warning",
            messages.ERROR: "error",
        }[level]

    def __str__(self):
        return self.message


@pytest.mark.unit
class TestHtmxMessagesMiddleware:
    def test_non_htmx_request_passes_through(self, factory):
        request = _request_with_messages(
            factory, htmx=False, level_pairs=[(messages.SUCCESS, "saved")]
        )
        response = HttpResponse()

        result = HtmxMessagesMiddleware(lambda r: response).process_response(request, response)

        assert "HX-Trigger" not in result

    def test_htmx_request_with_no_messages_passes_through(self, factory):
        request = _request_with_messages(factory, htmx=True)
        response = HttpResponse()

        result = HtmxMessagesMiddleware(lambda r: response).process_response(request, response)

        assert "HX-Trigger" not in result

    def test_htmx_request_drains_messages_into_show_toast(self, factory):
        request = _request_with_messages(
            factory,
            htmx=True,
            level_pairs=[
                (messages.SUCCESS, "Dispensed 5x Lantus"),
                (messages.WARNING, "Low stock"),
            ],
        )
        response = HttpResponse()

        result = HtmxMessagesMiddleware(lambda r: response).process_response(request, response)

        triggers = json.loads(result["HX-Trigger"])
        toasts = triggers["showToast"]
        assert toasts == [
            {"message": "Dispensed 5x Lantus", "kind": "success"},
            {"message": "Low stock", "kind": "warning"},
        ]

    def test_merges_with_existing_hx_trigger_dict(self, factory):
        request = _request_with_messages(factory, htmx=True, level_pairs=[(messages.SUCCESS, "ok")])
        response = HttpResponse()
        response["HX-Trigger"] = json.dumps({"inventory:changed": {"item_id": 7}})

        result = HtmxMessagesMiddleware(lambda r: response).process_response(request, response)

        triggers = json.loads(result["HX-Trigger"])
        assert triggers["inventory:changed"] == {"item_id": 7}
        assert triggers["showToast"][0]["message"] == "ok"

    def test_maps_debug_and_info_to_info_kind(self, factory):
        request = _request_with_messages(
            factory,
            htmx=True,
            level_pairs=[
                (messages.DEBUG, "trace"),
                (messages.INFO, "fyi"),
            ],
        )
        response = HttpResponse()

        result = HtmxMessagesMiddleware(lambda r: response).process_response(request, response)

        toasts = json.loads(result["HX-Trigger"])["showToast"]
        assert [t["kind"] for t in toasts] == ["info", "info"]
