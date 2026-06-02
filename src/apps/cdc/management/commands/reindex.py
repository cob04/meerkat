from django.core.management.base import BaseCommand

from apps.catalog.models import InventoryItem, StockMovement
from apps.cdc import transformers
from apps.cdc.opensearch_client import create_index, get_client, index_document


class Command(BaseCommand):
    help = "Rebuild the OpenSearch indexes from PostgreSQL (use after a mapping change)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--recreate", action="store_true", help="Drop and recreate the indexes first."
        )

    def handle(self, *args, **options):
        client = get_client()
        create_index(client, recreate=options["recreate"])

        items = 0
        for item_id in InventoryItem.objects.values_list("id", flat=True).iterator():
            action = transformers._build_inventory_doc(item_id)
            if action:
                index_document(client, action.doc_id, action.document, action.index)
                items += 1

        movements = 0
        for movement_id in StockMovement.objects.values_list("id", flat=True).iterator():
            action = transformers._build_movement_doc(movement_id)
            if action:
                index_document(client, action.doc_id, action.document, action.index)
                movements += 1

        self.stdout.write(
            self.style.SUCCESS(f"Reindexed {items} inventory and {movements} movement documents")
        )
