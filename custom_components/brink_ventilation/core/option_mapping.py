"""Build safe, language-independent mappings for Brink select options."""

from __future__ import annotations

from collections.abc import Iterable

from homeassistant.util import slugify


def build_option_state_map(
    options: Iterable[tuple[str, str]],
) -> tuple[dict[str, str], set[str]]:
    """Index normalized states without choosing between conflicting raw values.

    Each pair contains a raw device value and its label. Labels that normalize
    to the same key are safe only when they refer to the same raw value.
    Empty state keys and ambiguous choices are excluded from the writable map.
    """
    state_values: dict[str, str] = {}
    ambiguous_states: set[str] = set()
    for raw_value, label in options:
        state_key = slugify(label)
        if not state_key or state_key in ambiguous_states:
            continue
        previous_value = state_values.get(state_key)
        if previous_value is not None and previous_value != raw_value:
            del state_values[state_key]
            ambiguous_states.add(state_key)
            continue
        state_values[state_key] = raw_value
    return state_values, ambiguous_states
