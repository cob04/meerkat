from dataclasses import dataclass
from pathlib import Path

import pytest
from django.test import override_settings

from apps.catalog import rules


@dataclass
class FakeDrug:
    schedule: str = ""
    age_restricted: bool = False
    requires_prescription: bool = False
    storage_condition: str = "room_temperature"


@pytest.fixture
def rules_root(tmp_path) -> Path:
    folder = tmp_path / "dispensing"
    folder.mkdir()
    return tmp_path


def _write_rules(rules_root: Path, content: str) -> None:
    (rules_root / "dispensing" / "rules.yml").write_text(content)
    rules.reset_cache()


@pytest.mark.unit
class TestLoadRules:
    def test_returns_empty_when_namespace_missing(self, tmp_path):
        rules.reset_cache()
        with override_settings(RULES_DIR=tmp_path):
            assert rules.load_rules("missing") == []

    def test_parses_equals_rule(self, rules_root):
        _write_rules(
            rules_root,
            """
rules:
  - name: rx_required
    when: {field: requires_prescription, equals: true}
    then: {effect: require, message: needs rx}
""",
        )
        with override_settings(RULES_DIR=rules_root):
            loaded = rules.load_rules("dispensing")

        assert len(loaded) == 1
        assert loaded[0].name == "rx_required"
        assert loaded[0].operator == "equals"
        assert loaded[0].operand is True
        assert loaded[0].effect == "require"

    def test_parses_in_rule(self, rules_root):
        _write_rules(
            rules_root,
            """
rules:
  - name: ctrl
    when: {field: schedule, in: [II, III]}
    then: {effect: require, message: scheduled}
""",
        )
        with override_settings(RULES_DIR=rules_root):
            loaded = rules.load_rules("dispensing")

        assert loaded[0].operator == "in"
        assert loaded[0].operand == ["II", "III"]

    def test_unknown_effect_raises(self, rules_root):
        _write_rules(
            rules_root,
            """
rules:
  - name: bad
    when: {field: schedule, equals: I}
    then: {effect: explode, message: boom}
""",
        )
        with override_settings(RULES_DIR=rules_root):
            with pytest.raises(rules.RuleConfigError):
                rules.load_rules("dispensing")

    def test_missing_when_operator_raises(self, rules_root):
        _write_rules(
            rules_root,
            """
rules:
  - name: bad
    when: {field: schedule}
    then: {effect: warn, message: x}
""",
        )
        with override_settings(RULES_DIR=rules_root):
            with pytest.raises(rules.RuleConfigError):
                rules.load_rules("dispensing")


@pytest.mark.unit
class TestEvaluate:
    def test_equals_match_emits_action(self, rules_root):
        _write_rules(
            rules_root,
            """
rules:
  - name: rx
    when: {field: requires_prescription, equals: true}
    then: {effect: require, message: needs rx}
""",
        )
        with override_settings(RULES_DIR=rules_root):
            actions = rules.evaluate("dispensing", FakeDrug(requires_prescription=True))

        assert len(actions) == 1
        assert actions[0].rule == "rx"
        assert actions[0].effect == "require"
        assert actions[0].message == "needs rx"

    def test_no_match_emits_nothing(self, rules_root):
        _write_rules(
            rules_root,
            """
rules:
  - name: rx
    when: {field: requires_prescription, equals: true}
    then: {effect: require, message: needs rx}
""",
        )
        with override_settings(RULES_DIR=rules_root):
            actions = rules.evaluate("dispensing", FakeDrug(requires_prescription=False))

        assert actions == []

    def test_in_operator_matches_membership(self, rules_root):
        _write_rules(
            rules_root,
            """
rules:
  - name: ctrl
    when: {field: schedule, in: [II, III]}
    then: {effect: require, max_quantity: 30, message: scheduled}
""",
        )
        with override_settings(RULES_DIR=rules_root):
            assert rules.evaluate("dispensing", FakeDrug(schedule="II"))
            assert rules.evaluate("dispensing", FakeDrug(schedule="III"))
            assert rules.evaluate("dispensing", FakeDrug(schedule="IV")) == []

    def test_message_formats_with_field_and_metadata(self, rules_root):
        _write_rules(
            rules_root,
            """
rules:
  - name: ctrl
    when: {field: schedule, in: [II, III]}
    then:
      effect: require
      max_quantity: 30
      message: "Schedule {schedule} drugs limited to {max_quantity}"
""",
        )
        with override_settings(RULES_DIR=rules_root):
            actions = rules.evaluate("dispensing", FakeDrug(schedule="II"))

        assert actions[0].message == "Schedule II drugs limited to 30"
        assert actions[0].metadata == {"max_quantity": 30, "requires": None} or actions[
            0
        ].metadata == {"max_quantity": 30}

    def test_multiple_rules_can_fire(self, rules_root):
        _write_rules(
            rules_root,
            """
rules:
  - name: rx
    when: {field: requires_prescription, equals: true}
    then: {effect: require, message: rx}
  - name: cold
    when: {field: storage_condition, equals: refrigerated}
    then: {effect: warn, message: keep cold}
""",
        )
        with override_settings(RULES_DIR=rules_root):
            actions = rules.evaluate(
                "dispensing",
                FakeDrug(requires_prescription=True, storage_condition="refrigerated"),
            )

        effects = [a.effect for a in actions]
        assert "require" in effects
        assert "warn" in effects


@pytest.mark.unit
class TestRealRulesLoad:
    def test_seed_rules_parse(self):
        rules.reset_cache()
        loaded = rules.load_rules("dispensing")

        names = {r.name for r in loaded}
        assert "prescription_required" in names
        assert "schedule_one_block" in names
