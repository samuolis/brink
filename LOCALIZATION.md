# Localization guide

This document defines the localization contract for `brink_ventilation`.
[AI_POLICY.md](AI_POLICY.md) governs policy; [AGENTS.md](AGENTS.md) contains the
development workflow and verification commands. Follow
[home-assistant.md](home-assistant.md) for entity and action behavior.

## Catalog ownership and source of truth

| Resource | Purpose |
| --- | --- |
| `custom_components/brink_ventilation/translations/en.json` | Complete English runtime catalog and fallback |
| `custom_components/brink_ventilation/translations/nl.json` | Complete Dutch runtime catalog |
| `custom_components/brink_ventilation/translations/de.json` | Complete German runtime catalog |
| `custom_components/brink_ventilation/strings.json` | Maintained English source/fallback descriptions currently shared with the catalogs |
| `custom_components/brink_ventilation/translations.py` | Vendor text lookup used to interpret portal parameter names/options |
| `custom_components/brink_ventilation/services.yaml` | Action schemas, fields, selector configuration, and fallback labels |

This is a custom integration. Home Assistant reads the shipped locale files;
it does not compile this repository's `strings.json` or fetch its translations
from Lokalise. Keep `en.json` complete. The current `strings.json` is a partial
source file, not a second complete runtime catalog; keep overlapping English
entries consistent. Do not mistake `translations.py` for an additional locale.

The three supported locale files must have matching leaf-key sets. Adding a
language requires a complete catalog, translation review, and changes to every
supported-language list in the tests. Do not add an empty language file to imply
support.

## Separate names, states, and wire values

| Value | Example | Contract |
| --- | --- | --- |
| Entity translation key | `owner_group_name` | Stable entity-description key |
| Display name | `Owner group`, `Eigenaarsgroep`, `Eigentümergruppe` | Localized text |
| State/option key | `manual`, `cn1`, `very_low` | Language-independent state used by automations |
| Vendor label | `Manual`, `Relais output 1` | External API text, interpreted before exposing a state |
| Raw write value | `1`, `-2` | Numeric/string value sent using the vendor's `value_id` |

An entity needs a non-empty string at
`entity.<platform>.<translation_key>.name`. Checking only for the containing
object is insufficient. Reject empty objects, missing `name`, null/non-string
names, and whitespace-only names in completeness tests.

Keep user-supplied device names as user data. Do not translate registry unique
IDs, config-entry IDs, system IDs, parameter IDs, raw write values, or unit
symbols. Labels are presentation data; localized text must not drive control
logic or be persisted as the canonical option value.

## Supported state-key format

State translation keys must use lowercase letters, digits, and single internal
underscores or hyphens, without leading/trailing separators. Use descriptive
`snake_case` keys for new states. English display phrases, uppercase keys, spaces,
and leading-minus keys such as `-2` are invalid for these catalogs.

Existing dynamic select/enum labels are normalized with Home Assistant's
`slugify`. The catalog must contain the exact emitted key, including vendor
spelling. A corrected English label can produce a different state key and is
therefore a compatibility change. Prefer explicit, stable mappings when adding
new device capabilities, and test any fallback normalization.

| Vendor/native label | Exposed key |
| --- | --- |
| `Manual` | `manual` |
| `Automatic mode` | `automatic_mode` |
| `Relais output 1` | `relais_output_1` |
| `Only filtercondition` | `only_filtercondition` |
| `Supply fan off` | `supply_fan_off` |
| `Min. ventilation 50 m³/h` | `min_ventilation_50_m3_h` |
| External level `4` / `CN1` | `cn1` |

Preserve legitimate vendor aliases when they are emitted by supported devices.
Do not assume `relay_output_1` covers the distinct emitted key
`relais_output_1`. Detect ambiguous normalization collisions rather than choosing
a different raw device value silently.

The API extractor caches a unique state-to-value map and the set of ambiguous
keys for each parameter snapshot. Selects omit ambiguous choices, show an unknown
current state when it cannot be represented uniquely, and raise a translated
`ambiguous_option` error before writing. Raw legacy labels must pass the same
guard. Multiple labels for the same raw value may share one state safely.

For selects, every advertised option and current option must use the same key
representation. Reverse lookups must recover the original write value from both
cached and uncached parameter data. Negative humidity sensitivity values remain
negative on the wire while using semantic keys such as `very_low` in Home
Assistant. External CN1 is readable but must remain protected against writes.

For enum sensors, `native_value` must agree with `options`, and each supported
state must have a catalog entry. Unknown API values must not become a translated
healthy/dry/off state. Preserve Home Assistant's unknown/unavailable semantics.

Fan preset translations belong under each fan entity's
`state_attributes.preset_mode.state`. The exposed presets are `automatic`,
`manual`, `holiday`, `party`, and `night_ventilation`. Do not use the custom
integration's `entity_component` section as a substitute for entity translations;
that section is for entity-domain integrations and has a different schema.

## Writing labels

Use sentence case, clear terminology, and concise descriptions. Keep the Brink
brand and technical tokens such as `CO₂`, `CN1`, and `eBus` consistent. Avoid HTML,
leading/trailing whitespace, and text that embeds diagnostic implementation
details. Use the native numeric unit rather than adding a second unit to a name.

The following terminology distinguishes air paths; confirm the device parameter
definition before translating an ambiguous vendor label:

| Meaning | English | Dutch | German |
| --- | --- | --- | --- |
| Air supplied to rooms | Supply air | Toevoerlucht | Zuluft |
| Air extracted from rooms | Extract air | Afvoerlucht | Abluft |
| Outside air entering the unit | Outdoor air | Buitenlucht | Außenluft |
| Air discharged outdoors after exchange | Exhaust air | Afblaaslucht | Fortluft |
| Rotational speed | Fan speed | Toerental | Drehzahl |
| Volume flow | Airflow | Luchtdebiet | Luftvolumenstrom |

In particular, `No supply fan control` must refer to the **toevoerventilator** in
Dutch, not the afvoerventilator. Use `Wachtwoord`, `E-mailadres`, `Gatewaystatus`,
and `Apparaatstatus` consistently where applicable. Reauthentication success and
authentication errors must be fully localized rather than partly English.

Identical text across languages is not automatically an error: brand names,
protocol names, accepted technical loanwords, and unit symbols can be shared.
Semantic review is required; a blanket rule that every Dutch/German string must
differ from English produces false positives.

## Actions, selectors, and error messages

Keep action names/descriptions and field labels under `services`. Selector
labels, such as the four `brink_level` choices, belong under `selector`. Preserve
their actual values (`0..3`) and the `translation_key` link in `services.yaml`.
Home Assistant action calls must use stable keys, not the translated UI label.

User-facing errors must use `HomeAssistantError` or the appropriate subclass with
`translation_domain=DOMAIN`, a stable `translation_key`, and matching string
`translation_placeholders`. Store their messages under
`exceptions.<key>.message` in all three catalogs. For example:

```json
{
  "exceptions": {
    "unknown_option": {
      "message": "Option {option} is not supported for {parameter}."
    }
  }
}
```

Use named placeholders and keep the exact placeholder set in every language.
Validate their names as Python identifiers; do not wrap placeholders in single
quotes. Interpolate values through the supported exception API rather than
building an English message in code. Never put passwords, tokens, login HTML,
or unfiltered vendor error messages into placeholders.

Custom locale JSON must contain literal text, not unresolved
`[%key:...%]` references. Placeholders are supported; runtime reference expansion
for core's translation build is not available here. Use the current Home
Assistant schema for restrictions on URLs and other translation values.

## Change and migration procedure

1. Trace the description, vendor parameter, raw options, emitted state/preset,
   and reverse write lookup. Check every affected platform.
2. Add or update the English catalog and both translations in the same change.
   Keep duplicate JSON object keys out of the files.
3. Verify all description names and actual emitted states, not only parity
   between files: three equally incomplete files still pass a parity check.
4. Exercise representative API labels through entity lookup and writes. Cover
   explicit maps, cached maps, uncached options, aliases, invalid choices, and CN1.
5. Check placeholder parity and render the result with Home Assistant's actual
   translation loader. Loading successfully does not replace schema validation.
6. Run the checks in [AGENTS.md](AGENTS.md), including applicable hassfest
   validation. Do not hide invalid keys by relaxing the validator.
7. Document changed state values, select inputs, and presets in
   [docs/translation-migration.md](docs/translation-migration.md) and link the
   migration from the README when users need to update automations.

The existing tests cover entity-key/name completeness, matching catalogs,
placeholders, fixed and API-derived options, reverse writes, external control,
and actual Home Assistant loading. Keep the original completeness test and the
broader regressions complementary; do not delete one while fixing the other.
Tests of a method's legacy-input fallback alone do not establish compatibility
with validation performed by Home Assistant's full action/service path.

## Reference

Use the official [Home Assistant translation reference](https://contributors.home-assistant.io/core/integrations/translations/)
and the supported release's hassfest translation schema as primary references.
Repository catalogs and the verified device/API behavior determine the actual
keys this integration must ship.
