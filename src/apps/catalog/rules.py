from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from django.conf import settings

VALID_EFFECTS = {"warn", "require", "block"}


@dataclass
class Action:
    rule: str
    effect: str
    message: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class Rule:
    name: str
    description: str
    field: str
    operator: str
    operand: Any
    effect: str
    message: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def matches(self, value: Any) -> bool:
        if self.operator == "equals":
            return value == self.operand
        if self.operator == "in":
            return value in self.operand
        return False


class RuleConfigError(ValueError):
    """Raised when a rule file is malformed."""


def load_rules(namespace: str) -> list[Rule]:
    return _load_rules_cached(namespace, _rules_root_str())


def evaluate(namespace: str, subject: Any, context: dict[str, Any] | None = None) -> list[Action]:
    rules = load_rules(namespace)
    actions = []
    for rule in rules:
        value = _resolve_field(subject, rule.field)
        if not rule.matches(value):
            continue
        actions.append(_build_action(rule, subject, context or {}))
    return actions


def reset_cache() -> None:
    _load_rules_cached.cache_clear()


def _rules_root_str() -> str:
    return str(getattr(settings, "RULES_DIR", Path("rules")))


@lru_cache(maxsize=None)
def _load_rules_cached(namespace: str, rules_root: str) -> list[Rule]:
    folder = Path(rules_root) / namespace
    if not folder.is_dir():
        return []

    rules: list[Rule] = []
    for path in sorted(folder.glob("*.yml")):
        rules.extend(_parse_file(path))
    return rules


def _parse_file(path: Path) -> list[Rule]:
    raw = yaml.safe_load(path.read_text()) or {}
    entries = raw.get("rules", [])
    if not isinstance(entries, list):
        raise RuleConfigError(f"{path}: 'rules' must be a list")

    parsed = []
    for index, entry in enumerate(entries):
        try:
            parsed.append(_parse_rule(entry))
        except KeyError as exc:
            raise RuleConfigError(
                f"{path}: rule #{index + 1} missing required key {exc.args[0]}"
            ) from exc
    return parsed


def _parse_rule(entry: dict) -> Rule:
    when = entry["when"]
    then = entry["then"]
    effect = then["effect"]
    if effect not in VALID_EFFECTS:
        raise RuleConfigError(
            f"rule '{entry['name']}': unknown effect '{effect}'. "
            f"Expected one of {sorted(VALID_EFFECTS)}"
        )

    field_name = when["field"]
    if "equals" in when:
        operator, operand = "equals", when["equals"]
    elif "in" in when:
        operator, operand = "in", when["in"]
    else:
        raise RuleConfigError(f"rule '{entry['name']}': 'when' clause needs 'equals' or 'in'")

    metadata = {k: v for k, v in then.items() if k not in {"effect", "message"}}

    return Rule(
        name=entry["name"],
        description=entry.get("description", ""),
        field=field_name,
        operator=operator,
        operand=operand,
        effect=effect,
        message=then.get("message", ""),
        metadata=metadata,
    )


def _resolve_field(subject: Any, name: str) -> Any:
    if isinstance(subject, dict):
        return subject.get(name)
    return getattr(subject, name, None)


def _build_action(rule: Rule, subject: Any, context: dict[str, Any]) -> Action:
    payload = _flatten_subject(subject) | dict(rule.metadata) | dict(context)
    try:
        message = rule.message.format(**payload)
    except (KeyError, IndexError):
        message = rule.message
    return Action(
        rule=rule.name,
        effect=rule.effect,
        message=message,
        metadata=dict(rule.metadata),
    )


def _flatten_subject(subject: Any) -> dict[str, Any]:
    if isinstance(subject, dict):
        return dict(subject)
    return {k: v for k, v in vars(subject).items() if not k.startswith("_")}
