---
name: brink-fan-safety
description: Review and change Brink ventilation fan controls safely: legacy entity unique IDs, device-specific airflow limits, read/write permissions, level-zero turn-off and no-write regression tests.
---

# Brink fan identity and safe airflow control

Use for changes in `custom_components/brink_ventilation/fan.py`, airflow services, write metadata or fan entity identities.

## Preserve compatibility
- Read [AI_POLICY.md](../../../AI_POLICY.md), [AGENTS.md](../../../AGENTS.md) and [home-assistant.md](../../../home-assistant.md); inspect current `fan.py`, `const.py`, `entity.py` and `tests/test_fan.py`.
- Preserve the level fan's historic `..._fan` unique ID. The newly introduced continuous fan needs a **different** unique ID. For an unavoidable change, implement an explicit entity-registry migration with tests.
- Resolve each device by `system_id`, using the current coordinator snapshot. Never borrow a different system's data or assume every Brink device has the Flair 300 limits.

## Validate before a device write
- Writable ventilation levels are `0..3`; external `4` / `CN1` stays read-only. Preserve the current action's `0..300` m³/h schema while respecting stricter device bounds.
- Use each mode's current `min_value`, `max_value`, positive numeric `value_id` and `read_write` flag. `READ_WRITE_MAP` maps **integer 3** to `read-write`; reject booleans and malformed access fields.
- Apply the same writability validation both when selecting a level and immediately before writing it.
- Validate finite, supported, exact m³/h values; do **not** silently clamp 180 m³/h to a mode that tops out at 150. Reject unavailable modes before any write, including missing IDs, asymmetric limits and invalid capacity metadata.

## Level-zero semantics
- The discrete level fan may regard level zero as off. For the continuous fan, a validated positive level-zero airflow means **on**; zero means off; missing or invalid airflow remains unknown.
- To turn the continuous fan off, explicitly write **0 m³/h to the level-zero airflow parameter** and then set ventilation level to **0**. Never use a generic set-airflow(0) path that might select level one.
- Validate the level-zero metadata and writability before issuing either write. A failed multi-call sequence is not atomic; do not claim a new state on partial failure.

## Focused regression matrix
- Assert the original fan unique ID survives and the new fan does not collide.
- Test level-zero airflow positive/zero/missing/negative/boolean/NaN; changed coordinator snapshots; different fan capacities.
- Test read-only, hidden, missing and wrong-type access metadata; invalid `value_id`; bounds excluding zero; asymmetric supported ranges.
- For a valid turn-off assert **exact ordered writes**, and for invalid metadata assert **no writes** to any level. Ensure external CN1 is never written.
- Run exact-head Python 3.14/HA matrix and Ruff. Mock vendor transport; never issue device commands as a regression test.
