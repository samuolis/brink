---
name: brink-regression-ci
description: Build deterministic Brink Home Assistant regression tests and verify Python 3.14, Home Assistant 2026.7.0/2026.10.3, Ruff, HACS and hassfest on the actual final PR head.
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
- Work in Python 3.14 and separate clean environments for each required Home Assistant release. The declared minimum is **2026.7.0**; the baseline is **2026.10.3**.
```shell
python -m pip install -r requirements_test_minimum.txt
python -m pytest -q
# In a separate fresh environment:
python -m pip install -r requirements_test.txt
python -m pytest -q
```
- Run **Ruff 0.17.3** using the exact lint and formatting commands in `AGENTS.md`. New maintained test files must be included in both scoped workflow commands and documentation.
- Avoid aliased `asyncio.TimeoutError` (UP041; use built-in `TimeoutError`) and nested context managers flagged by SIM117; `ruff check` success is **not** `ruff format --check` success.
- Inspect `git diff --check` and all changed files. Do not loosen test gates to achieve a green check.

## Check the exact GitHub head
1. Fetch the PR's **current** head SHA after your final push.
2. Verify Ruff, pytest on both HA versions, HACS and hassfest on that same SHA; read the job logs for actual passed/failed counts.
3. Ignore success from superseded commits. GitHub concurrency cancellation, skipped jobs and `mergeable: true` are not passing test evidence.
4. Document actual commands/versions, any unavailable environment and remaining physical-device or end-to-end risks; do not merge or release without authorization.

Documentation-only edits require frontmatter, internal-link, diff and CI checks where available; do not claim Python tests were run if only documentation was changed.
