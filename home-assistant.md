# Home Assistant integration engineering

These requirements apply to `custom_components/brink_ventilation/`. They work
with the architecture, commands, and CI agreements in [AGENTS.md](AGENTS.md),
the localization contract in [LOCALIZATION.md](LOCALIZATION.md), and the governing
[AI_POLICY.md](AI_POLICY.md).

## Supported behavior and compatibility evidence

The manifest identifies a `device` integration using `cloud_polling`, with a
config flow and the `sensor`, `binary_sensor`, `fan`, `number`, and `select`
platforms. Account access uses Brink's portal client. A local HTTP client and UID
decoders also exist, but the active config flow does not select a local transport.

Python 3.14 is the development target. Home Assistant `2026.7.0` is the declared
minimum, providing the `UnitOfRatio.PARTS_PER_MILLION` API used by CO₂ entities.
The minimum-version test requirements and the `2026.10.3` baseline have matching
fixture packages; the `2026.11.1` compatibility environment uses the official
`pytest-homeassistant` fixtures in a separate, pinned environment. Run all
three environments for compatibility changes as described in `AGENTS.md`.
Recheck official APIs when changing lifecycle, flows, entities,
or dependencies, and update the minimum, tests, and user-facing requirements
together when introducing a newer API.

## Setup, runtime data, and unload

- Validate account input, polling options, and authentication before creating an
  entry or exposing platforms. Reject invalid intervals with a useful flow error.
- Await the first coordinator refresh before forwarding entry setup. Distinguish
  permanent authentication failure from temporary connection/setup failure.
- Map credential rejection to `ConfigEntryAuthFailed`; use `ConfigEntryNotReady`
  for retryable setup failures and `UpdateFailed` for polling failures. Preserve
  cancellation rather than converting it into a normal update failure.
- Keep setup failure atomic: release integration-owned resources, avoid orphaned
  platform listeners/tasks, and leave Home Assistant able to retry.
- Await platform forwarding and unloading. Only discard runtime data after a
  successful unload; a failed unload must not leave active entities without data.
- Register cleanup callbacks for listeners and background tasks when they are
  introduced. Stop and await owned tasks during unload/reload.

Runtime currently uses `hass.data[DOMAIN][entry.entry_id]`. The preferred direction
is a typed runtime container on `ConfigEntry.runtime_data`, with one consistent
ownership model across setup, platforms, reload, and unload. Make that migration
as a complete tested change; avoid supporting two conflicting runtime stores.

Use the established config-entry APIs to update entry data and options. Do not
mutate entry dictionaries in place or recreate an entry as a substitute for
reauthentication. Keep the existing account-identity normalization/mismatch guard
unless a documented config-entry migration changes it. A credential update must
not silently bind the entry to another account or duplicate registered devices.

## Sessions, authentication, and polling

Inject the Home Assistant-managed aiohttp session into the API client and retain
its TLS, proxy, and connection-pooling behavior. Do not close a session owned by
Home Assistant. The current client's `close()` clears sensitive client state;
resource ownership must remain explicit if additional sessions are introduced.

Keep token refresh synchronized with the existing lock and bounded request
timeouts. Ensure response bodies/connections are consumed or released on every
path. Authentication redirects must remain on the trusted HTTPS origin before
credentials or tokens are forwarded. Local-device HTTP is a separately validated
transport, not permission to weaken cloud authentication.

Use one coordinator update path per entry. Select a justified polling interval
and bounded concurrency; entity count must not multiply upstream requests.
Avoid concurrent conflicting writes to a device and uncontrolled refresh loops.
After a successful write, update/refresh through the coordinator consistently.
Do not publish success or a new optimistic state after the write failed.

Retry policy must distinguish reads, explicit authentication rejection, rate
limits, and writes with uncertain outcomes. A timed-out write may have reached
the device; do not blindly repeat it. Respect upstream rate-limit signals when
adding retry behavior, and make retries testable without sleeping in tests.

## Cached state and availability

Use `CoordinatorEntity` and the typed device snapshot. Resolve the entity's own
`system_id`; never use the first item from coordinator data. Properties such as
`available`, `native_value`, `options`, and `extra_state_attributes` must be quick
reads over cached data, with no I/O or scheduling side effects.

Keep these conditions distinct:

| Condition | Required behavior |
| --- | --- |
| API request failure | Coordinator reports the failure; expose sanitized API health information |
| Device offline | Device-dependent entities become unavailable according to their description |
| Blocking device alert | Respect existing control/availability protection and retain diagnostic visibility |
| Missing/unusable parameter | Unknown/unavailable value, not an invented zero or normal state |
| Valid numeric zero | Preserve the confirmed measurement |
| Empty/missing coordinator snapshot | Safe device lookup; no attribute/key exception |
| Recovery | Restore availability without creating duplicate devices or entities |

Diagnostic entities may need to remain available to explain an outage. Do not
derive all diagnostic availability solely from the same failing parameter they
describe. Precompute shared blocking-alert state during snapshot creation when
appropriate, and read expensive aggregate properties once per formatter call.

Fan capacity must follow the latest coordinator snapshot, including recovery
after an empty snapshot and later metadata changes. Validate a positive finite
whole-number maximum before converting percentages to m³/h; missing or invalid
capacity must not fall back to a guessed 300 m³/h. Expose an unknown percentage
and reject affected writes with a translated error. A missing or invalid level
must remain unknown and omit level-dependent airflow attributes. Keep shared
preset definitions immutable and return a caller-owned list from entity getters.

For `active_alert_count`, preserve a valid non-negative integer portal summary,
including zero. Otherwise compute the count during normalization from the complete
active, unarchived alert list for that system. Fetch all pages with a finite
request limit; malformed records, incomplete/changing totals, and repeated pages
must fail the refresh rather than yield zero or a partial count. This diagnostic
remains readable for offline devices and blocking alerts when the API refresh
succeeds. API failures still make it unavailable.

## Entities, identity, and units

- Use entity descriptions and `has_entity_name` for predictable translated names.
  Follow `LOCALIZATION.md` for stable state and preset keys.
- Preserve device identifiers and entity unique IDs across restarts, reauth,
  display-name edits, locale changes, and device ordering. Test migrations before
  changing an existing identifier format.
- Use the actual device/system ID as identity; keep email addresses and user
  labels out of new entity unique IDs and public debug output.
- Choose entity platform, device class, state class, native unit, precision,
  category, and default enablement from the parameter's actual semantics.
- Use native units and conversion helpers consistently: airflow is m³/h,
  pressure is Pa, humidity is %, temperature is °C, and fan rotation is rpm where
  those are the documented parameter units. Do not add a second conversion in
  the entity after a UID parser has already applied scaling.
- Use `extra_state_attributes`, not the deprecated `device_state_attributes`.
  Keep attributes stable, useful, bounded in size, and free of sensitive raw
  payloads. Translation keys and exception details are not a privacy exemption.
- Unknown vendor enum values must remain unknown rather than selecting a healthy
  state by default. Every non-unknown enum value must belong to its options.

## Actions and writable parameters

The integration actions are `set_airflow` and `set_level`; platforms also expose
their normal fan, number, and select actions. Keep `services.yaml`, registration
schemas, handlers, selectors, translations, and tests consistent.

Validate input before the request. Check integer/numeric types, finiteness,
effective range, allowed option, device capability, write access, and a usable
vendor `value_id`. Do not infer writability from the existence of an entity or
from its translated name. Unsupported/read-only values must not reach Brink.

Maintain the level `0..3` contract and the external level `4`/`cn1` guard. Use
device capability limits for airflow and number entities. UI slider steps do
not replace server-side input validation. Do not assume every model shares the
Flair 300's capacity or parameter IDs.

Use raw vendor values in writes while exposing stable keys to Home Assistant.
For a fan preset update, obtain the operating-mode parameter payload; the
`_operating_mode` property returns a state value, not a dictionary with `value_id`.
Cover successful writes and all rejection paths, including missing metadata and
negative sensitivity values where the vendor mapping permits them.

Raise useful translated action errors through Home Assistant's exception APIs.
Pass the domain, key, and named placeholders; keep raw upstream exceptions and
authentication material out of UI messages. A lower-layer log message is not a
substitute for an actionable, safe error at the action boundary.

## Async and Python behavior

Use Home Assistant's async APIs and await their completion. Avoid blocking
`requests`, `time.sleep`, synchronous file access, or blocking subprocess calls
on the event loop. Move unavoidable blocking work to an appropriate executor,
and keep Home Assistant state changes on the Home Assistant event loop.

Create tasks through the appropriate Home Assistant lifecycle API and keep
ownership/cleanup explicit. Do not create an untracked task for an entity
property or hide a task exception. Respect cancellation during shutdown and
reload. Use `asyncio` timeouts and concurrency tools supported by the declared
Python/Home Assistant pair; migrations away from legacy helpers require tests.

Use timezone-aware timestamps at external boundaries and UTC for stored instants.
Do not guess a timezone for a naive vendor timestamp without an explicit API
contract. Test offsets and daylight-saving transitions when introducing temporal
calculations. Apply the typing and dataclass requirements in `AGENTS.md`.

## Logging and diagnostics

Log outage/recovery transitions with an appropriate severity and useful context.
Avoid logging the same expected connection failure once per entity or every
poll with an unrestricted traceback. Use module loggers and lazy `%` arguments.

Follow `AI_POLICY.md` before formatting any vendor data. Prefer a safe error
category, HTTP status, count, or endpoint template. Existing raw payload logging
is debt to remove in scoped hardening work, not a pattern to copy. Audit both
logs and entity attributes/diagnostics because upstream error text can contain
account, device, network, or authentication information.

## Local decoding, derived data, and icons

Use `core/uid_definitions.py` as the local decoding contract. Validate byte counts
and byte ranges, endianness, signedness, scaling, enum values, and units. Test
malformed/unknown UIDs and negative temperatures. Do not guess that a local UID
and a cloud `numeric_id` are interchangeable.

Sound-power entities are estimates from reference coefficients. Label them as
estimates and preserve the model's units and reference range. Do not describe a
computed estimate as a measured sound-pressure reading. Validate missing/non-finite
inputs and justify using a coefficient set with another device model.

Before adding or changing an `mdi:` icon, verify that its exact name exists in
the [Material Design metadata](https://raw.githubusercontent.com/Templarian/MaterialDesign/master/meta.json)
and is supported by the targeted Home Assistant frontend. Validate conditional
and fallback branches too. Do not invent an icon by appending suffixes to a known
name. Follow the official entity/device-class icon rules when a custom icon is
unnecessary.

## Quality target and known gaps

Platinum is the target; this repository must not claim to have achieved it without
evidence for every applicable prerequisite and rule. Evaluate the quality scale
incrementally and document justified non-applicability when formal tracking is
introduced.

| Area | Current limitation or required follow-up |
| --- | --- |
| Formal quality status | No `quality_scale.yaml` or evidence of completed Bronze/Silver/Gold/Platinum requirements |
| Runtime data | Uses `hass.data`; typed `ConfigEntry.runtime_data` migration remains separate work |
| Client boundary | Cloud client is embedded in the integration; async dependency and transport contracts need explicit evaluation |
| Compatibility | Minimum `2026.7.0`, baseline `2026.10.3`, and new `2026.11.1` use separate pinned test environments; physical device coverage and future releases need separate evidence |
| Automated verification | Python 3.14 pytest matrix, scoped Ruff, HACS, and hassfest workflows exist; repository-wide strict typing remains separate work |
| Workflow supply chain | Action references are pinned; upstream HACS/hassfest validator images remain rolling and can introduce new rules |
| Lifecycle coverage | Existing tests do not establish comprehensive config-flow/setup/unload, auth-retry, or physical-device coverage |
| Data/privacy hardening | Legacy raw-payload logs and loosely typed vendor boundaries require further audit |
| Local support | Local client/UID utilities do not establish a complete local config-entry lifecycle |

These gaps are not completed tasks and do not authorize unrelated bulk changes.
Address relevant risks within the requested scope and report the evidence and
remaining limitations honestly.

## Primary references

- [Config entries](https://contributors.home-assistant.io/core/integrations/config-entries/)
- [Config flow](https://contributors.home-assistant.io/core/integrations/config-flow/)
- [Fetching data and coordinators](https://contributors.home-assistant.io/core/integrations/fetching-data/)
- [Setup failures and exceptions](https://contributors.home-assistant.io/core/integrations/setup-failures/)
- [Async in Home Assistant](https://contributors.home-assistant.io/core/internals/asyncio/)
- [Integration quality scale](https://contributors.home-assistant.io/core/quality-scale/)
- [Async dependency](https://contributors.home-assistant.io/core/quality-scale/async-dependency/)
- [Injected web session](https://contributors.home-assistant.io/core/quality-scale/inject-websession/)
- [Strict typing](https://contributors.home-assistant.io/core/quality-scale/strict-typing/)
- [Icons](https://contributors.home-assistant.io/core/entities/icons/)

Use the source and documentation for the actual supported release when behavior
differs from the current documentation. Never infer API availability solely from
a method name or an older integration example.
