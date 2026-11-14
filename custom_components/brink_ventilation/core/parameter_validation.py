"""Safely validate write access and remove private vendor parameter metadata."""

from __future__ import annotations

from collections.abc import Mapping
from math import isfinite

from ..const import READ_WRITE_MAP


def is_parameter_writable(parameter: Mapping[str, object] | None) -> bool:
    """Accept only explicit integer read-write permission from Brink."""
    if not isinstance(parameter, Mapping):
        return False
    access = parameter.get("read_write")
    return (
        isinstance(access, int)
        and not isinstance(access, bool)
        and READ_WRITE_MAP.get(access) == "read-write"
    )


def writable_value_id(parameter: Mapping[str, object] | None) -> int | None:
    """Return a positive writable vendor value ID, or None for unsafe metadata."""
    if not is_parameter_writable(parameter) or parameter is None:
        return None
    raw_id = parameter.get("value_id")
    if isinstance(raw_id, bool) or not isinstance(raw_id, (int, str)):
        return None
    try:
        identifier = int(raw_id)
    except (TypeError, ValueError, OverflowError):
        return None
    return identifier if identifier > 0 else None


def finite_parameter_bounds(
    parameter: Mapping[str, object] | None,
) -> tuple[float, float] | None:
    """Return finite min/max values without inventing unsupported device limits."""
    if not isinstance(parameter, Mapping):
        return None
    lower = parameter.get("min_value")
    upper = parameter.get("max_value")
    if (
        lower is None
        or upper is None
        or isinstance(lower, bool)
        or isinstance(upper, bool)
    ):
        return None
    try:
        minimum, maximum = float(lower), float(upper)
    except (TypeError, ValueError, OverflowError):
        return None
    if not (isfinite(minimum) and isfinite(maximum) and minimum <= maximum):
        return None
    return minimum, maximum


_PRIVATE_ATTRIBUTES = frozenset(
    {
        "name",
        "raw_name",
        "value",
        "_raw_value",
        "default_value",
        "numeric_id",
        "value_id",
        "component_id",
        "list_items",
        "options",
        "options_str",
        "raw_options",
        "raw_value",
        "unit_of_measure",
    }
)


def redacted_parameter_attributes(
    attributes: dict[str, object],
) -> dict[str, object]:
    """Omit private portal payload fields, retaining safe diagnostic categories."""
    return {
        key: value
        for key, value in attributes.items()
        if key not in _PRIVATE_ATTRIBUTES
    }
