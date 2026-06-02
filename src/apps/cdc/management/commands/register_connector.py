import json
import logging
import time

import requests
from django.conf import settings
from django.core.management.base import BaseCommand

logger = logging.getLogger(__name__)

CONNECT_URL = "http://connect:8083"
CONNECTOR_NAME = "meerkat-connector"


class Command(BaseCommand):
    help = "Register the Debezium PostgreSQL connector"

    def add_arguments(self, parser):
        parser.add_argument(
            "--delete",
            action="store_true",
            help="Delete the connector instead of creating it",
        )

    def handle(self, *args, **options):
        if options["delete"]:
            self._delete_connector()
            return

        self._wait_for_connect()
        self._register_connector()

    def _wait_for_connect(self, retries=10, delay=3):
        for attempt in range(retries):
            try:
                response = requests.get(f"{CONNECT_URL}/")
                if response.ok:
                    self.stdout.write(f"Connect API is ready")
                    return
            except requests.ConnectionError:
                pass
            self.stdout.write(f"Waiting for Connect API... ({attempt + 1}/{retries})")
            time.sleep(delay)
        raise RuntimeError("Connect API did not become available")

    def _build_config(self) -> dict:
        db = settings.DATABASES["default"]
        return {
            "name": CONNECTOR_NAME,
            "config": {
                "connector.class": "io.debezium.connector.postgresql.PostgresConnector",
                "database.hostname": db["HOST"],
                "database.port": db["PORT"],
                "database.user": db["USER"],
                "database.password": db["PASSWORD"],
                "database.dbname": db["NAME"],
                "topic.prefix": "meerkat",
                "table.include.list": (
                    "public.catalog_inventoryitem,"
                    "public.catalog_product,"
                    "public.catalog_drug,"
                    "public.catalog_location,"
                    "public.catalog_stockmovement"
                ),
                "plugin.name": "pgoutput",
                "publication.autocreate.mode": "filtered",
                "slot.name": "meerkat_slot",
                "key.converter": "org.apache.kafka.connect.json.JsonConverter",
                "key.converter.schemas.enable": "false",
                "value.converter": "org.apache.kafka.connect.json.JsonConverter",
                "value.converter.schemas.enable": "false",
                "tombstones.on.delete": "false",
                "snapshot.mode": "initial",
            },
        }

    def _register_connector(self):
        config = self._build_config()
        url = f"{CONNECT_URL}/connectors/{CONNECTOR_NAME}/config"
        response = requests.put(
            url,
            headers={"Content-Type": "application/json"},
            data=json.dumps(config["config"]),
        )

        if response.ok:
            self.stdout.write(self.style.SUCCESS(f"Connector '{CONNECTOR_NAME}' registered"))
        else:
            self.stderr.write(f"Failed to register connector: {response.status_code}")
            self.stderr.write(response.text)
            raise RuntimeError("Connector registration failed")

    def _delete_connector(self):
        response = requests.delete(f"{CONNECT_URL}/connectors/{CONNECTOR_NAME}")
        if response.ok:
            self.stdout.write(self.style.SUCCESS(f"Connector '{CONNECTOR_NAME}' deleted"))
        elif response.status_code == 404:
            self.stdout.write(f"Connector '{CONNECTOR_NAME}' not found")
        else:
            self.stderr.write(f"Failed to delete connector: {response.status_code}")
