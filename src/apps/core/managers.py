from django.db import models


class SoftDeleteQuerySet(models.QuerySet):
    def delete(self):
        raise NotImplementedError("Use soft_delete() instead of delete().")

    def alive(self):
        return self.filter(deleted_at__isnull=True)

    def dead(self):
        return self.filter(deleted_at__isnull=False)


class SoftDeleteManager(models.Manager):
    def get_queryset(self) -> SoftDeleteQuerySet:
        return SoftDeleteQuerySet(self.model, using=self._db).alive()

    def all_with_deleted(self) -> SoftDeleteQuerySet:
        return SoftDeleteQuerySet(self.model, using=self._db)

    def deleted_only(self) -> SoftDeleteQuerySet:
        return SoftDeleteQuerySet(self.model, using=self._db).dead()
