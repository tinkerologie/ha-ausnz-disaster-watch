"""Checks of quality_scale.yaml and icons.json (#21).

hassfest validates quality_scale.yaml only for core integrations, so these tests apply the
same rules: every rule listed once, valid statuses, a comment on each exemption, and the
manifest tier backed by its rules.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
import yaml

from custom_components.ausnz_disaster_watch.geo_location import hazard_translation_key
from custom_components.ausnz_disaster_watch.models import CanonicalHazard, HazardType
from custom_components.ausnz_disaster_watch.sensor import FIRE_DANGER_OPTIONS, WARNING_LEVEL_OPTIONS_WITH_CLEAR

INTEGRATION = Path(__file__).parent.parent / "custom_components" / "ausnz_disaster_watch"

# Rule names and tiers of script/hassfest/quality_scale.py (Home Assistant 2026.10)
TIERS: dict[str, tuple[str, ...]] = {
    "bronze": (
        "action-setup",
        "appropriate-polling",
        "brands",
        "common-modules",
        "config-flow",
        "config-flow-test-coverage",
        "dependency-transparency",
        "docs-actions",
        "docs-conditions",
        "docs-high-level-description",
        "docs-installation-instructions",
        "docs-removal-instructions",
        "docs-triggers",
        "entity-event-setup",
        "entity-unique-id",
        "has-entity-name",
        "runtime-data",
        "test-before-configure",
        "test-before-setup",
        "unique-config-entry",
    ),
    "silver": (
        "action-exceptions",
        "config-entry-unloading",
        "docs-configuration-parameters",
        "docs-installation-parameters",
        "entity-unavailable",
        "integration-owner",
        "log-when-unavailable",
        "parallel-updates",
        "reauthentication-flow",
        "test-coverage",
    ),
    "gold": (
        "devices",
        "diagnostics",
        "discovery",
        "discovery-update-info",
        "docs-data-update",
        "docs-examples",
        "docs-known-limitations",
        "docs-supported-devices",
        "docs-supported-functions",
        "docs-troubleshooting",
        "docs-use-cases",
        "dynamic-devices",
        "entity-category",
        "entity-device-class",
        "entity-disabled-by-default",
        "entity-translations",
        "exception-translations",
        "icon-translations",
        "reconfiguration-flow",
        "repair-issues",
        "stale-devices",
    ),
    "platinum": ("async-dependency", "inject-websession", "strict-typing"),
}


def _status(value: Any) -> str:
    return value["status"] if isinstance(value, dict) else value


@pytest.fixture(name="rules")
def rules_fixture() -> dict[str, Any]:
    """Return the rules of quality_scale.yaml."""
    return yaml.load((INTEGRATION / "quality_scale.yaml").read_text(encoding="utf-8"), UniqueKeyLoader)["rules"]


class UniqueKeyLoader(yaml.SafeLoader):
    """A safe YAML loader that rejects a key listed twice instead of keeping the last one."""

    def construct_mapping(self, node: yaml.MappingNode, deep: bool = False) -> dict[Any, Any]:
        """Build the mapping, failing on a duplicate key."""
        keys = [self.construct_object(key, deep=deep) for key, _ in node.value]
        if duplicates := {key for key in keys if keys.count(key) > 1}:
            raise yaml.constructor.ConstructorError(None, None, f"duplicate keys {sorted(duplicates)}", node.start_mark)
        return super().construct_mapping(node, deep=deep)


def test_duplicate_rule_is_rejected() -> None:
    """A rule listed twice fails to load instead of the second silently winning."""
    with pytest.raises(yaml.constructor.ConstructorError, match="duplicate keys"):
        yaml.load("rules:\n  brands: done\n  brands: todo\n", UniqueKeyLoader)


def test_every_rule_is_listed(rules: dict[str, Any]) -> None:
    """The file lists exactly the hassfest rules."""
    assert set(rules) == {rule for tier in TIERS.values() for rule in tier}


def test_rule_values_are_valid(rules: dict[str, Any]) -> None:
    """Statuses are done, todo or exempt; exemptions and todos say why."""
    for name, value in rules.items():
        assert _status(value) in {"done", "todo", "exempt"}, name
        if isinstance(value, dict):
            assert set(value) <= {"status", "comment"}, name
        if _status(value) in {"exempt", "todo"}:
            assert isinstance(value, dict), name
            assert str(value.get("comment", "")).strip(), name


def test_manifest_tier_is_met(rules: dict[str, Any]) -> None:
    """Every rule of the manifest's tier and the tiers below it is done or exempt."""
    manifest = json.loads((INTEGRATION / "manifest.json").read_text(encoding="utf-8"))
    declared = manifest["quality_scale"]
    for tier, names in TIERS.items():
        assert all(_status(rules[name]) in {"done", "exempt"} for name in names), tier
        if tier == declared:
            break
    else:
        pytest.fail(f"Unknown tier {declared}")


def test_every_hazard_type_has_a_map_icon(mock_hazard_emergency_warning: CanonicalHazard) -> None:
    """Each hazard type's geolocation translation key has an icon."""
    icons = json.loads((INTEGRATION / "icons.json").read_text(encoding="utf-8"))["entity"]["geo_location"]
    for hazard_type in HazardType:
        hazard = mock_hazard_emergency_warning.model_copy(update={"hazard_type": hazard_type})
        assert hazard_translation_key(hazard) in icons, hazard_type


def test_icons_match_translated_entities() -> None:
    """icons.json names only real sensors and covers each one without a device class icon."""
    icons = json.loads((INTEGRATION / "icons.json").read_text(encoding="utf-8"))["entity"]
    translations = json.loads((INTEGRATION / "translations" / "en.json").read_text(encoding="utf-8"))["entity"]
    source = "\n".join(path.read_text(encoding="utf-8") for path in INTEGRATION.glob("*.py"))
    for platform in ("sensor", "binary_sensor"):
        assert set(icons[platform]) <= set(translations[platform]), platform
    # No icon is set in code; every icon comes from icons.json
    assert "_attr_icon" not in source
    assert 'icon="mdi:' not in source
    assert "def icon(self)" not in source


def test_enum_states_are_translated_and_have_icons() -> None:
    """Every option of the ENUM sensors has a translated name, and state icons name real options (#21)."""
    icons = json.loads((INTEGRATION / "icons.json").read_text(encoding="utf-8"))["entity"]["sensor"]
    translations = json.loads((INTEGRATION / "translations" / "en.json").read_text(encoding="utf-8"))["entity"]
    for key, options in (
        ("highest_warning_level", WARNING_LEVEL_OPTIONS_WITH_CLEAR),
        ("fire_danger_rating", FIRE_DANGER_OPTIONS),
    ):
        assert set(translations["sensor"][key]["state"]) == set(options), key
        assert set(icons[key]["state"]) <= set(options), key
