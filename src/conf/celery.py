import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "conf.settings.dev")

app = Celery("meerkat")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
