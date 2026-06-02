import json
import logging
import signal

from confluent_kafka import Consumer, KafkaError

from apps.cdc.broker import get_consumer_config
from apps.cdc.opensearch_client import (
    delete_document,
    get_client,
    index_document,
)
from apps.cdc.transformers import (
    TOPIC_DRUG,
    TOPIC_INVENTORY,
    TOPIC_LOCATION,
    TOPIC_MOVEMENT,
    TOPIC_PRODUCT,
    DeleteAction,
    IndexAction,
    transform,
)

logger = logging.getLogger(__name__)

TOPICS = [TOPIC_INVENTORY, TOPIC_PRODUCT, TOPIC_DRUG, TOPIC_LOCATION, TOPIC_MOVEMENT]


def run_consumer():
    config = get_consumer_config(group_id="meerkat-cdc-consumer")
    consumer = Consumer(config)
    os_client = get_client()
    running = True

    def shutdown(signum, frame):
        nonlocal running
        logger.info("Shutting down consumer...")
        running = False

    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)

    consumer.subscribe(TOPICS)
    logger.info("Subscribed to topics: %s", TOPICS)

    try:
        while running:
            msg = consumer.poll(timeout=1.0)
            if msg is None:
                continue
            if msg.error():
                if msg.error().code() == KafkaError._PARTITION_EOF:
                    continue
                logger.error("Consumer error: %s", msg.error())
                continue

            try:
                value = json.loads(msg.value().decode("utf-8"))
                topic = msg.topic()

                actions = transform(topic, value)
                for action in actions:
                    if isinstance(action, IndexAction):
                        index_document(os_client, action.doc_id, action.document, action.index)
                    elif isinstance(action, DeleteAction):
                        delete_document(os_client, action.doc_id, action.index)

                consumer.commit(message=msg)

            except Exception:
                logger.exception("Error processing message from %s", msg.topic())

    finally:
        consumer.close()
        logger.info("Consumer closed")
