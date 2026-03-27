from django.core.management.base import BaseCommand

from apps.cdc.tasks import run_cdc_consumer


class Command(BaseCommand):
    help = "Dispatch the CDC consumer Celery task"

    def handle(self, *args, **options):
        run_cdc_consumer.delay()
        self.stdout.write(self.style.SUCCESS("CDC consumer task dispatched"))
