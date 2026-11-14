# Contributor and agent instructions

These instructions apply to the whole repository. Read [AI_POLICY.md](AI_POLICY.md)
first; it is the governing repository policy. Read any applicable parent or nested
instruction files before working. The specialist requirements are in
[LOCALIZATION.md](LOCALIZATION.md) and [home-assistant.md](home-assistant.md).

## Repository map and current architecture

The Home Assistant integration domain is `brink_ventilation`; its source is under
`custom_components/brink_ventilation/`. The default branch is `master`.

| Area | Responsibility |
| --- | --- |
| `__init__.py` | Entry setup/unload, platform forwarding, and integration action registration |
| `config_flow.py` | Account login, reauthentication, and polling options |
| `core/brink_home_cloud.py` | Brink portal HTTP/OIDC, token handling, requests, and parameter extraction |
| `core/option_mapping.py` | Safe normalized option indexing and collision detection |
| `api.py` | Combine systems, devices, alerts, and parameters into device snapshots |
| `models.py` | Device/alert models, enums, and shared value objects |
| `coordinator.py` | Polling, update failures, authentication failures, and API health |
| `entity.py` | Entity/device identity, device lookup, and shared availability helpers |
| `sensor.py`, `binary_sensor.py`, `fan.py`, `number.py`, `select.py` | Platform descriptions and entity behavior |
| `core/brink_home_local.py`, `core/uid_*.py` | Local transport and UID definitions/decoding; not a config-flow-selected transport |
| `const.py` | Domain constants, vendor identifiers, and state/parameter mappings |
| `translations.py` | Vendor text lookup used during API extraction |
| `translations/*.json`, `strings.json`, `services.yaml` | Home Assistant catalogs, source/fallback strings, and action descriptions |
| `sound.py` | Sound-power estimation using reference coefficients |
| `tests/` | Behavior, performance, and localization regressions |
| `.github/workflows/` | Python tests, Ruff, HACS, and hassfest validation |

The active flow is cloud polling through `BrinkHomeCloud`, aggregation into
`dict[int, BrinkDeviceData]`, coordinator caching, and entity reads. Runtime
objects currently live in `hass.data[DOMAIN][entry.entry_id]`. A future migration
to typed `ConfigEntry.runtime_data` must update setup, platforms, unload, and
tests together; do not describe that migration as already implemented.

## Working sequence

1. Read the governing documents, current branch/PR head, project structure, and
   affected source and tests. Use `rg` and `rg --files` for searches.
2. Establish the actual behavior and a focused regression scenario. Reproduce a
   reported failure before claiming its cause when the environment permits it.
3. Identify public contracts: registry IDs, state keys, options, units, actions,
   configuration schemas, and vendor write values.
4. Make the smallest cohesive correction. Avoid unrelated formatting, dependency
   updates, identifier changes, and speculative new abstractions.
5. Update the relevant catalogs and documentation in the same change.
6. Run the applicable checks below. Fix regressions introduced by the change and
   report genuine baseline or environmental limitations.
7. Review the complete diff, refresh the remote head, preserve concurrent work,
   and publish under the branch-integrity rules in `AI_POLICY.md`.
8. Verify the published result and report the exact state of its checks.

Do not replace an existing PR's tree with files from an older checkout. Retain
review fixes and existing regression tests when combining automated changes.

## Architecture rules

- Keep HTTP/authentication in the client and normalized data in `api.py`/models.
  Keep Home Assistant lifecycle and exception mapping in the integration layer.
- Poll through the coordinator. Entity properties must read cached data and
  perform no network I/O, filesystem I/O, blocking work, or task scheduling.
- Resolve a device by `system_id` through `_device` or a keyed dictionary lookup.
  Never select the first device from an iterator as a substitute for identity.
- Compute snapshot-wide derived information, such as blocking-alert status,
  during normalization when practical. Reuse a fetched aggregate locally rather
  than repeatedly allocating lists in state/attribute getters.
- Preserve the precomputed option/reverse-option lookup paths. Keep fallback
  paths compatible with uncached data, and test both paths after changing them.
- Keep derived caches scoped to the snapshot or immutable description they
  describe. Do not change frozen dataclass equality/hash semantics to add a cache.
- Centralize parameter and enum mappings. When editing legacy duplicate
  definitions in `const.py`, inspect the effective definition and its consumers;
  do not add another shadowing definition.
- Keep local UID parsing independent of Home Assistant and cloud account state.
  Adding a usable local transport requires lifecycle/configuration tests, not
  only the presence of the local client class.

## Python standards

Python 3.14 is the development target. Respect the Python version required by the
Home Assistant release under test, and verify API support before adopting it.

- Add accurate type hints to new or materially changed functions, methods,
  callbacks, and shared structures. Match the real sync/async return type.
- Use `list`, `dict`, `set`, `tuple`, `X | None`, and `collections.abc` interfaces.
  Do not introduce `typing.List` or `typing.Dict`. Keep `Any` at unvalidated
  external boundaries and narrow it before domain logic.
- Use descriptive `snake_case` function/variable names and private helpers with
  a leading underscore. Do not shadow parameters, built-ins, or outer-scope names.
- Give modules, classes, functions, methods, and test helpers useful docstrings.
  Describe units, ownership, failure behavior, or non-obvious constraints rather
  than repeating the name. Document a changed public behavior.
- Follow the surrounding Python layout, with two blank lines before top-level
  definitions. Keep formatting changes focused on the edited code.
- Put required dataclass fields before defaulted fields. Prefer explicit,
  keyword-only descriptions and immutable value objects where appropriate.
- Use timezone-aware datetimes. Use `datetime.now(timezone.utc)` rather than
  `utcnow()`, and use monotonic time for elapsed durations when appropriate.
- Handle expected exceptions at the boundary responsible for recovery. Preserve
  cancellation, and avoid broad catches in business logic. Do not silently return
  plausible data after a parsing, authentication, or write failure.
- Use lazy `%` formatting in logger calls. Do not use f-strings or eager `%`/`format`
  evaluation in logging calls. Apply the privacy rules before logging arguments.
- Avoid dead code, duplicate implementations, blanket lint suppression, and
  `type: ignore` comments that hide an unresolved contract mismatch.

Existing untyped or legacy code is not evidence that new code may omit these
requirements. Modernize touched behavior coherently without an unrelated rewrite.

## Validation and device contracts

Validate external JSON shapes, identifiers, timestamps, numeric conversions,
finite values, byte ranges, and capability metadata before using them. Do not
treat booleans as valid measurements merely because they subclass `int`.
Preserve legitimate zero, negative values where the domain permits them, and
the distinction between missing, unknown, unavailable, and confirmed measurements.

Keep these identifiers distinct: `system_id` identifies a device/system;
`parameter_key` is the integration's semantic key; `numeric_id` is vendor
metadata; `value_id` identifies a writable vendor value. Device writes must use
the correct `value_id`, not a display name or translation key.

Validate ventilation levels against `0..3`. Treat external level `4`/`cn1` as
read-only. The registered airflow action currently exposes `0..300` m³/h;
respect effective device limits as well, and document any capability-driven
change to that public range. Reject unsupported writes before contacting Brink.

## Compatibility and documentation

Registry unique IDs, config-entry identity/version, raw vendor writes, native
units, entity device/state classes, exposed state keys, and action schemas are
compatibility contracts. A spelling or translation edit can still change a
contract if the state is derived from the vendor label.

For a breaking change, include its migration, before/after values, tests, and
release-facing explanation. Keep [docs/translation-migration.md](docs/translation-migration.md)
accurate for state/option/preset changes. Update `README.md` for installation,
configuration, supported capabilities, or user-visible behavior changes.

Keep programming standards, architecture rules, test commands, documentation
requirements, and CI/CD agreements in this file. Keep policy in `AI_POLICY.md`.
Use the specialist documents for detailed localization and Home Assistant
requirements; update their cross-references when responsibilities change.

## Environment and executable checks

Run from the repository root in a Python 3.14 virtual environment. On Windows,
use the environment's `Scripts/python.exe`; on POSIX, use `bin/python`, or activate
the environment so `python` resolves to it. Avoid machine-specific absolute paths
in repository scripts or documentation.

```shell
python --version
python -m pip install -r requirements_test.txt
python -m pytest -q
```

The 2026.7.0 and 2026.10.3 requirements pin the legacy
`pytest-homeassistant-custom-component` fixtures. Home Assistant 2026.11
provides the official `pytest-homeassistant` fixtures; do not install
both pytest plugins in one environment because their fixtures overlap.
`tests/ha_test_support.py` selects the installed package's `MockConfigEntry`
helper without changing integration behavior. Inspect the resolved versions,
and verify `pip check` rather than assuming the installed Core version.
`pytest.ini` sets `asyncio_mode = auto`; retain proper async fixture handling.

The declared Home Assistant minimum is `2026.7.0`. When changing compatibility or
Home Assistant APIs, run the complete suite in a separate clean Python 3.14
environment using the minimum-version requirements:

```shell
python -m pip install -r requirements_test_minimum.txt
python -m pytest -q
```

That file pins Home Assistant `2026.7.0` and its matching fixture package. Use
separate environments for `requirements_test.txt` (`2026.10.3`) and
`requirements_test_2026_11.txt` (`2026.11.1`), which uses the official
`pytest-homeassistant` plugin. Verify `pip check` and the actual installed
Home Assistant version in each environment.

For focused localization work:

```shell
python -m pytest -q tests/test_translations.py tests/test_translation_regressions.py
```

Ruff is a separate development tool. The baseline used for these commands is
Ruff `0.17.3`; install that version when reproducing the tooling environment:

```shell
python -m pip install ruff==0.17.3
python -m ruff check --select E9,F63,F7,F82 custom_components tests
python -m ruff check tests/test_translations.py tests/test_translation_regressions.py tests/test_active_alerts.py tests/test_fan.py tests/test_coordinator_lifecycle.py tests/test_entry_lifecycle.py tests/test_issue20_hardening.py tests/ha_test_support.py custom_components/brink_ventilation/fan.py custom_components/brink_ventilation/core/option_mapping.py custom_components/brink_ventilation/core/parameter_validation.py
python -m ruff format --check tests/test_translations.py tests/test_translation_regressions.py tests/test_active_alerts.py tests/test_fan.py tests/test_coordinator_lifecycle.py tests/test_entry_lifecycle.py tests/test_issue20_hardening.py tests/ha_test_support.py custom_components/brink_ventilation/core/option_mapping.py custom_components/brink_ventilation/core/parameter_validation.py
git diff --check
```

There is no repository-wide `pyproject.toml`, mypy configuration, or Pylint
configuration at this baseline. Do not invent configured gates or claim that
these focused commands establish full-repository formatting/typing compliance.
New Python files must pass Ruff's default lint and formatting checks. Introduce
broader gates with an explicit configuration and a reviewed baseline.

## Required test coverage by change

| Changed behavior | Meaningful cases to verify |
| --- | --- |
| Login or refresh | Invalid credentials versus temporary failure, bounded refresh/retry, concurrent refresh, cancellation, redacted logs |
| Entry lifecycle/options | First-refresh failure, successful setup/unload, reload, reauth identity, invalid polling interval, resource cleanup |
| Parameter extraction | Malformed/missing data, duplicate/raw options, supported IDs, unknown values, cached and uncached lookup |
| Select/enum/fan translation | Every emitted key, all three languages, loader behavior, stable/legacy input handling, preserved numeric writes |
| Device actions | Valid input, unsupported input, missing `value_id`, bounds, external CN1, negative sensitivity values, no write after validation failure |
| Availability | API versus device status, empty snapshots, multiple devices, faults, recovery, valid zero versus unknown |
| UID decoding | Byte length/range, signed values, endianness, scales/units, malformed and unknown UIDs |
| Sound estimation | Reference ranges, units, clamping behavior, unavailable inputs, model applicability |

Tests must be deterministic, use synthetic data, and avoid live Brink traffic.
Use the real Home Assistant helpers where their behavior matters. Mock transport
boundaries rather than replacing the behavior under test. Do not add tests that
merely repeat implementation details. For documentation-only edits, validate
links, commands, factual claims, and the diff; run behavior tests when code or
test fixtures also change.

## Reusable agent skills

Project procedures are available as discoverable Agent Skills in `.agents/skills/`.
Use the relevant skill for a task; `AI_POLICY.md`, this file and applicable
specialist instructions remain authoritative.

| Skill | Scope |
| --- | --- |
| [PR review](.agents/skills/brink-pr-review/SKILL.md) | Review findings, thread resolution and safe fork updates |
| [Fan safety](.agents/skills/brink-fan-safety/SKILL.md) | Device writes, entity IDs and airflow behavior |
| [Cloud privacy](.agents/skills/brink-cloud-privacy/SKILL.md) | OAuth secrets, API exceptions and private logging |
| [Regression and CI](.agents/skills/brink-regression-ci/SKILL.md) | Synthetic test design and exact-head validation |

These skills add task workflows, not new policy or proof of execution.
## Regression lessons from November 2026 Brink reviews

These checks came from the follow-up to
[samuolis/brink#37](https://github.com/samuolis/brink/pull/37) and the focused
[security/fan](https://github.com/HiDiHo01/brink/pull/17) and
[lifecycle/coordinator](https://github.com/HiDiHo01/brink/pull/18) PRs.
Apply them to related changes; an open PR or a passing synthetic test is not
proof that physical-device behavior has been verified.

- **Keep existing fan identities stable.** When splitting a fan into discrete
  level and continuous-airflow entities, keep the original `..._fan` unique ID
  on the equivalent legacy entity. Give the new entity a distinct ID. Test
  registry identity and the absence of duplicate IDs; otherwise implement an
  explicit, tested migration before changing existing identifiers.
- **Do not equate level zero with zero airflow for every fan.** A positive
  level-zero setpoint may still move air. Continuous-airflow `is_on` and
  `turn_off` must agree with the device's validated airflow and actual
  writes; preserve discrete-level semantics and the external `CN1` guard.
  Test positive, zero, missing, invalid, and recovery cases, including the
  exact commands issued when turning the continuous fan off.
- **Do not silently clamp an airflow request.** Read each writable mode's
  `min_value`, `max_value` and `value_id` from the *current* device
  snapshot; validate numeric types and finiteness and select a mode that
  actually supports the requested m³/h. Reject unsupported targets before
  any partial write. Include asymmetric level limits, different capacities,
  valid zero and missing metadata in regression tests. Preserve the declared
  service range unless a documented schema change accompanies it.
- **Exercise privacy at the log boundary.** OAuth token responses, account
  and owner-group fields, raw system/device payloads, serial numbers, private
  URLs and raw upstream exception text must not reach INFO *or* DEBUG logs.
  Assert this with synthetic sentinel values and `caplog`; keep diagnostic
  messages useful through safe error categories, counts and HTTP statuses.
- **Test setup and polling failure ownership separately.** Verify failed
  login, HTTP 401 versus retryable HTTP/connection/timeout failures, the
  initial coordinator refresh, successful recovery, and `CancelledError`
  propagation. Assert that failures do not forward platforms or leave
  orphaned entry runtime state, that owned clients close on failed setup,
  and that an unsuccessful platform unload retains the live runtime/client.
  Prefer a real coordinator and Home Assistant fixtures for state behavior;
  mock only network and external service boundaries where practical.
- **Run both Ruff phases on new Python tests.** With Ruff 0.17.3 and Python
  3.14, prefer built-in `TimeoutError` over its `asyncio` alias (UP041)
  and combine nested context managers (SIM117). Passing
  `ruff check` does *not* imply `ruff format --check` passes. Apply the
  formatter, then rerun both checks rather than weakening the gate.
- **Trust only checks for the current PR head.** Success on a previous commit
  is stale after a push, and GitHub concurrency can cancel superseded runs.
  Confirm Ruff, both declared HA test versions, HACS and hassfest for the exact
  head SHA. Report test counts from job logs, distinguish mocked versus live
  verification, and mark skipped/pending jobs accurately.
- **Handle fork-to-upstream PRs deliberately.** If an upstream PR's head is the
  fork's `master`, prepare corrections in a separate fork branch and review
  them against that fork's `master`. Merging the corrective PR there updates
  the existing upstream PR; merely opening it does not. A GitHub 403
  permission error is not a published review. Do not merge, force-rebase or
  claim an upstream update without verification and authorization.

## CI/CD and dependency agreements

The checked-in workflows run on pull requests targeting `master`, pushes to
`master`, weekly schedules, and manual dispatch:

| Workflow | Checks |
| --- | --- |
| `.github/workflows/ci.yml` | Python 3.14 pytest matrix for Home Assistant `2026.7.0`, `2026.10.3`, and `2026.11.1`, dependency consistency/version checks, and the Ruff commands above |
| `.github/workflows/hacs.yml` | HACS integration packaging without PR comments |
| `.github/workflows/hassfest.yml` | Full upstream Home Assistant integration validation, including applicable translation schemas |

The test matrix uses separate minimum, baseline, and 2026.11 requirement files. Keep
its expected Home Assistant versions aligned with those files; the workflow
fails if the installed version differs. Ruff `0.17.3` enforces the documented
critical-error and focused regression baseline, not repository-wide formatting.

Workflows use read-only repository permissions, finite job timeouts, concurrency
cancellation, and checkouts without persisted credentials. Action references are
pinned to verified full commit SHAs. HACS and hassfest still use upstream rolling
validator images internally, so a pinned action does not freeze validator rules.
Keep local results separate from CI results: a workflow file's existence does
not prove that it executed or passed for a particular commit.

- Keep HACS and full hassfest validation applicable to relevant changes. A run
  of only hassfest's translation validator must be reported with that scope.
- New or revised workflows must use least-privilege permissions, trusted actions
  pinned to verified full commit SHAs, and safe handling of untrusted PR input.
- Do not use `pull_request_target` to execute untrusted PR code with credentials.
  Do not add duplicate workflows or weaken required checks to obtain green CI.
- Keep test dependency installation reproducible and compatible with the declared
  Python/Home Assistant pair. Update pins, tests, and compatibility claims together.
- When updating an action pin, verify its source commit and supported inputs.
  Review upstream validator changes rather than suppressing new findings.
- Review the published commit's check results. Report failures, skipped jobs,
  missing runs, and pending reviews accurately; do not equate mergeability with
  correctness. Do not merge or release unless the session authorizes it.

## Completion report

State what changed and why, identify affected user contracts and migrations,
summarize the actual verification and versions, and link the PR or commit.
Highlight any untested physical-device behavior, known baseline failures, or
remaining compatibility limitations. See the current quality gaps in
[home-assistant.md](home-assistant.md); do not claim an achieved quality tier
without evidence for all applicable requirements.
