from datetime import datetime, timezone as dt_timezone
from unittest.mock import MagicMock, patch

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.catalog.models import Product
from apps.core.managers import SoftDeleteManager
from apps.core.middleware import CurrentUserMiddleware, get_current_user
from apps.core.models import AuditEvent

User = get_user_model()


def _mock_user(**kwargs):
    mock = MagicMock(spec=User, **kwargs)
    state = MagicMock()
    state.db = "default"
    mock._state = state
    return mock


@pytest.mark.unit
class TestSoftDeleteBehaviour:
    def _make_product(self):
        return Product(
            name="Test Product",
            sku="TEST-001",
            unit_price=10,
        )

    def test_is_deleted_false_by_default(self):
        product = self._make_product()
        assert product.is_deleted is False

    def test_is_deleted_true_when_deleted_at_set(self):
        product = self._make_product()
        product.deleted_at = timezone.now()
        assert product.is_deleted is True

    def test_delete_raises_not_implemented(self):
        product = self._make_product()
        with pytest.raises(NotImplementedError, match="soft_delete"):
            product.delete()

    @patch("apps.core.models.get_current_user", return_value=None)
    @patch("apps.core.models.timezone")
    def test_soft_delete_sets_fields(self, mock_tz, mock_get_user):
        product = self._make_product()
        mock_now = datetime(2026, 3, 24, tzinfo=dt_timezone.utc)
        mock_tz.now.return_value = mock_now
        product.save = MagicMock()

        user = _mock_user()
        product.soft_delete(user=user)

        assert product.deleted_at == mock_now
        assert product.deleted_by == user
        product.save.assert_called_once_with(
            update_fields=["deleted_at", "deleted_by", "updated_at"]
        )

    def test_restore_clears_fields(self):
        product = self._make_product()
        product.deleted_at = timezone.now()
        product.deleted_by = _mock_user()
        product.save = MagicMock()

        product.restore()

        assert product.deleted_at is None
        assert product.deleted_by is None
        product.save.assert_called_once_with(
            update_fields=["deleted_at", "deleted_by", "updated_at"]
        )


@pytest.mark.unit
class TestTrackableBehaviour:
    @patch("apps.core.models.get_current_user")
    def test_save_sets_created_by_on_new_instance(self, mock_get_user):
        user = _mock_user()
        mock_get_user.return_value = user

        product = Product(name="Test", sku="T-001", unit_price=10)

        with patch("django.db.models.Model.save"):
            product.save()

        assert product.created_by == user
        assert product.updated_by == user

    @patch("apps.core.models.get_current_user")
    def test_save_sets_only_updated_by_on_existing_instance(self, mock_get_user):
        user = _mock_user()
        original_creator = _mock_user()
        mock_get_user.return_value = user

        product = Product(name="Test", sku="T-001", unit_price=10)
        product.pk = 1
        product.created_by = original_creator

        with patch("django.db.models.Model.save"):
            product.save()

        assert product.created_by == original_creator
        assert product.updated_by == user

    @patch("apps.core.models.get_current_user")
    def test_save_skips_user_when_no_current_user(self, mock_get_user):
        mock_get_user.return_value = None

        product = Product(name="Test", sku="T-001", unit_price=10)

        with patch("django.db.models.Model.save"):
            product.save()

        assert product.created_by is None
        assert product.updated_by is None


@pytest.mark.unit
class TestAuditEvent:
    def test_str_representation(self):
        event = AuditEvent(action="create", model_name="Product", record_id=42)
        assert str(event) == "create on Product#42"

    def test_save_raises_on_existing_record(self):
        event = AuditEvent(action="create", model_name="Product", record_id=42)
        event.pk = 1

        with pytest.raises(NotImplementedError, match="immutable"):
            event.save()

    def test_delete_raises(self):
        event = AuditEvent(action="create", model_name="Product", record_id=42)

        with pytest.raises(NotImplementedError, match="cannot be deleted"):
            event.delete()

    def test_save_allowed_on_new_record(self):
        event = AuditEvent(action="create", model_name="Product", record_id=42)

        with patch.object(AuditEvent.__mro__[1], "save") as mock_save:
            event.save()
            mock_save.assert_called_once()


@pytest.mark.unit
class TestCurrentUserMiddleware:
    def test_get_current_user_returns_none_by_default(self):
        with patch("apps.core.middleware._thread_local", MagicMock(spec=[])):
            assert get_current_user() is None

    def test_process_request_stores_user(self):
        middleware = CurrentUserMiddleware(get_response=lambda r: None)
        request = MagicMock()
        user = MagicMock()
        user.is_authenticated = True
        request.user = user

        middleware.process_request(request)

        assert get_current_user() == user

    def test_process_response_clears_user(self):
        middleware = CurrentUserMiddleware(get_response=lambda r: None)
        request = MagicMock()
        user = MagicMock()
        user.is_authenticated = True
        request.user = user

        middleware.process_request(request)
        middleware.process_response(request, MagicMock())

        assert get_current_user() is None

    def test_get_current_user_returns_none_for_anonymous(self):
        middleware = CurrentUserMiddleware(get_response=lambda r: None)
        request = MagicMock()
        user = MagicMock()
        user.is_authenticated = False
        request.user = user

        middleware.process_request(request)

        assert get_current_user() is None


@pytest.mark.unit
class TestSoftDeleteManager:
    @patch("apps.core.managers.SoftDeleteQuerySet")
    def test_get_queryset_filters_alive(self, mock_qs_class):
        manager = SoftDeleteManager()
        manager.model = MagicMock()
        manager._db = "default"

        mock_qs = MagicMock()
        mock_qs_class.return_value = mock_qs

        manager.get_queryset()

        mock_qs.alive.assert_called_once()

    @patch("apps.core.managers.SoftDeleteQuerySet")
    def test_all_with_deleted_returns_unfiltered(self, mock_qs_class):
        manager = SoftDeleteManager()
        manager.model = MagicMock()
        manager._db = "default"

        mock_qs = MagicMock()
        mock_qs_class.return_value = mock_qs

        result = manager.all_with_deleted()

        assert result == mock_qs
        mock_qs.alive.assert_not_called()

    @patch("apps.core.managers.SoftDeleteQuerySet")
    def test_deleted_only_filters_dead(self, mock_qs_class):
        manager = SoftDeleteManager()
        manager.model = MagicMock()
        manager._db = "default"

        mock_qs = MagicMock()
        mock_qs_class.return_value = mock_qs

        manager.deleted_only()

        mock_qs.dead.assert_called_once()
