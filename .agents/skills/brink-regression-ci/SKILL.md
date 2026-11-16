---
name: brink-regression-ci
description: Build deterministic Brink Home Assistant regression tests, handle pinned legacy/official pytest fixture compatibility, and verify Python 3.14 with HA 2026.7.0/2026.10.3/2026.11.0, Ruff, HACS and hassfest on the final PR head.
---

# Brink regression tests and CI validation

Use for test additions, CI failures, new Python modules or a merge-readiness check. Repository rules in [AGENTS.md](../../../AGENTS.md) and [AI_POLICY.md](../../../AI_POLICY.md) remain authoritative.

## Design effective tests
- Inspect relevant production code and existing `tests/` before editing. Reproduce still-existing bugs with minimal synthetic data, not just implementation-shape assertions.
- Use `MockConfigEntry`, a real `BrinkCoordinator` and Home Assistant fixtures when state semantics or lifecycle matter; mock network boundaries with `AsyncMock`. Never make live Brink API calls or physical writes.
- For setup: invalid credentials and HTTP 401 versus HTTP 503/timeout/network errors, first-refresh failure, successful forwarding, owned-client closure, unload failure retaining runtime and cancellation.
- For coordinator: API status transitions, error category/HTTP code, sanitized exception causes, recovered diagnostics and propagated `CancelledError`.
- For fans: numeric bounds, explicit write permission, exact vendor IDs, current capacity, CN1, stable unique IDs and no device writes when rejected.
- For privacy: synthetic sentinel tokens and URLs must be absent from `caplog`, including rendered tracebacks.

## Run the configured verification
- Work in Python 3.14 and separate clean environments for every declared Home Assistant release. The minimum is **2026.7.0**, the baseline **2026.10.3**, and the additional matrix release **2026.11.0**.
```shell
python -m pip install -r requirements_test_minimum.txt
python -m pytest -q
# In a separate fresh environment:
python -m pip install -r requirements_test.txt
python -m pytest -q
# In a third clean environment for Home Assistant 2026.11.0:
python -m pip install -r requirements_test_2026_11.txt
python -m pip check
python -c 'import homeassistant; import pytest; raise SystemExit(pytest.main(["-q"]))'
```
- Verify each environment with `python -m pip check` and `importlib.metadata.version('homeassistant')` against its exact pinned release. Run **Ruff 0.17.3** using the exact lint and formatting commands in `AGENTS.md`. New maintained test files must be included in both scoped workflow commands and documentation.
- Avoid aliased `asyncio.TimeoutError` (UP041; use built-in `TimeoutError`) and nested context managers flagged by SIM117; `ruff check` success is **not** `ruff format --check` success.
- Inspect `git diff --check` and all changed files. Do not loosen test gates to achieve a green check.

## Pinned fixture migration and HTTPX import ordering

- **Honor exact dependency pins.** The legacy
  `pytest-homeassistant-custom-component==0.13.374` required
  `homeassistant==2026.10.3`. Official
  `pytest-homeassistant==2026.11.0` required
  `homeassistant==2026.11.0`; neither could be installed with HA
  `2026.11.1` at the time of PR #22. Do not force incompatible packages with
  `--no-deps` or claim support for an untested patch release. Verify matching
  Core/fixture requirements for each future release.
- **Keep fixture families isolated.** Use the official pytest plugin only in
  the dedicated 2026.11 environment and the custom-component plugin only in
  older environments. Get `MockConfigEntry` from `tests/ha_test_support.py`.
  Both plugins in one environment can register conflicting fixtures.
- **Run Core initialization before pytest plugins on 2026.11.** Otherwise a
  plugin can import `httpx` before Home Assistant calls
  `httpx2.alias_httpx()`, preventing pytest collection. Use the conditional
  CI command and documented CLI invocation above; revisit it when dependencies
  change. Do not mute the startup error or disable tests.
- **Inspect warnings separately from failures.** The original successful
  2026.11.0 run passed 601 tests and reported six warnings attributable to
  pytest assertion rewriting and HA/third-party deprecations. Track their
  origin; do not label that release as warning-free or claim device testing.

## Check the exact GitHub head
1. Fetch the PR's **current** head SHA after your final push.
2. Verify Ruff, pytest on **all declared HA versions**, HACS and hassfest on that same SHA; read the job logs for actual passed/failed counts **and warnings**.
3. Ignore success from superseded commits. GitHub concurrency cancellation, skipped jobs and `mergeable: true` are not passing test evidence.
4. Document actual commands/versions, any unavailable environment and remaining physical-device or end-to-end risks; do not merge or release without authorization.

Documentation-only edits require frontmatter, internal-link, diff and CI checks where available; do not claim Python tests were run if only documentation was changed.
