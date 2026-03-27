from django.core.management.base import BaseCommand

from apps.cdc.opensearch_client import INVENTORY_INDEX, create_index, get_client


class Command(BaseCommand):
    help = "Create the OpenSearch inventory index"

    def add_arguments(self, parser):
        parser.add_argument(
            "--recreate",
            action="store_true",
            help="Delete and recreate the index",
        )

    def handle(self, *args, **options):
        client = get_client()
        create_index(client, recreate=options["recreate"])
        self.stdout.write(self.style.SUCCESS(f"Index '{INVENTORY_INDEX}' ready"))
