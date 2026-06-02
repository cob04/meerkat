from django.core.management.base import BaseCommand

from apps.catalog.models import InventoryItem
from apps.cdc import transformers
from apps.cdc.opensearch_client import create_index, get_client, index_document


class Command(BaseCommand):
    help = "Rebuild the OpenSearch inventory index from PostgreSQL (use after a mapping change)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--recreate", action="store_true", help="Drop and recreate the index first."
        )

    def handle(self, *args, **options):
        client = get_client()
        create_index(client, recreate=options["recreate"])

        count = 0
        for item_id in InventoryItem.objects.values_list("id", flat=True).iterator():
            action = transformers._build_inventory_doc(item_id)
            if action:
                index_document(client, action.doc_id, action.document)
                count += 1

        self.stdout.write(self.style.SUCCESS(f"Reindexed {count} inventory documents"))
