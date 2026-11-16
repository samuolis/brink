"""Tests for Brink ventilation translation completeness."""

from __future__ import annotations

import json
from pathlib import Path

from custom_components.brink_ventilation.binary_sensor import (
    BINARY_SENSOR_DESCRIPTIONS,
)
from custom_components.brink_ventilation.fan import (
    FAN_DESCRIPTION,
    VENTILATION_FAN_DESCRIPTION,
)
from custom_components.brink_ventilation.number import NUMBER_DESCRIPTIONS
from custom_components.brink_ventilation.select import SELECT_DESCRIPTIONS
from custom_components.brink_ventilation.sensor import SENSOR_DESCRIPTIONS

TRANSLATIONS_DIR = (
    Path(__file__).parent.parent
    / "custom_components"
    / "brink_ventilation"
    / "translations"
)


def _get_entity_translation_keys_by_domain() -> dict[str, set[str]]:
    """Return all translation keys grouped by domain."""
    domain_keys: dict[str, set[str]] = {
        "sensor": set(),
        "binary_sensor": set(),
        "select": set(),
        "number": set(),
        "fan": set(),
    }

    for desc in SENSOR_DESCRIPTIONS:
        if desc.translation_key:
            domain_keys["sensor"].add(desc.translation_key)

    for desc in BINARY_SENSOR_DESCRIPTIONS:
        if desc.translation_key:
            domain_keys["binary_sensor"].add(desc.translation_key)

    for desc in SELECT_DESCRIPTIONS:
        if desc.translation_key:
            domain_keys["select"].add(desc.translation_key)

    for desc in NUMBER_DESCRIPTIONS:
        if desc.translation_key:
            domain_keys["number"].add(desc.translation_key)

    for desc in (FAN_DESCRIPTION, VENTILATION_FAN_DESCRIPTION):
        if desc.translation_key:
            domain_keys["fan"].add(desc.translation_key)

    return domain_keys


def test_entity_translation_keys_exist_in_all_languages() -> None:
    """Require every entity key to have a non-empty name in all three locales."""
    domain_keys = _get_entity_translation_keys_by_domain()

    for lang in ["en", "nl", "de"]:
        json_file = TRANSLATIONS_DIR / f"{lang}.json"
        assert json_file.exists(), f"Translation file {json_file} does not exist"

        with open(json_file, encoding="utf-8") as f:
            data = json.load(f)

        entities = data.get("entity", {})

        for domain, keys in domain_keys.items():
            domain_entities = entities.get(domain, {})
            missing_keys = keys - set(domain_entities.keys())
            assert not missing_keys, (
                f"Language '{lang}' missing entity translation keys for '{domain}': {sorted(missing_keys)}"
            )

            for key in keys:
                entry = domain_entities[key]
                assert (
                    isinstance(entry, dict)
                    and isinstance(entry.get("name"), str)
                    and entry["name"].strip()
                ), (
                    f"Language '{lang}' entity translation key '{domain}.{key}' is missing a non-empty 'name' string"
                )
