import pytest

from apps.cdc.broker import get_consumer_config


@pytest.mark.unit
class TestBrokerConfig:
    def test_consumer_config_has_required_keys(self, settings):
        settings.BROKER_BOOTSTRAP_SERVERS = "localhost:9092"
        config = get_consumer_config("test-group")

        assert config["bootstrap.servers"] == "localhost:9092"
        assert config["group.id"] == "test-group"
        assert config["auto.offset.reset"] == "earliest"
        assert config["enable.auto.commit"] is False
