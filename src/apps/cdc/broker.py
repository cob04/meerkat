from django.conf import settings


def get_consumer_config(group_id: str) -> dict:
    return {
        "bootstrap.servers": settings.BROKER_BOOTSTRAP_SERVERS,
        "group.id": group_id,
        "auto.offset.reset": "earliest",
        "enable.auto.commit": False,
    }
