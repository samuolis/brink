---
name: brink-cloud-privacy
description: Audit and fix secret leakage in Brink OAuth and HTTP API client, sanitized error propagation, coordinator logging, private URLs and synthetic caplog regression tests.
---

# Brink cloud privacy and exception safety

Use when editing `core/brink_home_cloud.py`, `api.py`, `coordinator.py`, token handling, logging, health diagnostics or security review findings.

## Identify sensitive data
- Read [AI_POLICY.md](../../../AI_POLICY.md), [home-assistant.md](../../../home-assistant.md), [AGENTS.md](../../../AGENTS.md) and the current implementation.
- Access and refresh tokens, passwords, authorization headers, PKCE codes/verifiers, owner groups, device names, serial numbers, private URLs/query strings and raw response/request bodies must not appear in INFO, WARNING, DEBUG, exception logs or state attributes.
- Prefer safe status codes, operation categories, bounded retry counts and exception **type names**. Do not log raw response objects or unsanitized upstream exception messages.

## Inspect the full error chain
1. Follow errors from aiohttp request to `BrinkApiError`, `BrinkCoordinator._async_update_data()`, Home Assistant traceback logging and exposed diagnostic fields.
2. At the sanitization boundary, retain safe HTTP status/error kind while suppressing untrusted original exception text in the rendered traceback (use `raise ... from None` where needed).
3. Check the HTTP failure, connector failure and exhausted-retry branches. Keep authentication failures distinct from transient errors; preserve task cancellation and bounded retries.
4. Do not broadly remove useful error codes or change transport/session ownership as a side effect of redaction.

## Synthetic regression verification
- Build synthetic sentinel secrets in a mocked token response, private system/owner payload, HTTP URL query and original exception message. **Never use a real account or real device response**.
- Assert with `caplog` at DEBUG and ERROR that no sentinel leaks through direct logger arguments **or rendered chained exceptions**.
- Exercise the actual cloud request path and, when log behavior matters, a real coordinator with a mocked API transport; test connector, HTTP 5xx and exhausted retries.
- Verify status classifications and error-code preservation as well as recovery clearing stale coordinator health fields. Mock retry sleeping, not failure classification.
- Re-run Ruff, the Python 3.14/HA test matrix, HACS and hassfest on the final commit. Clearly label mocked-vs-live coverage.
