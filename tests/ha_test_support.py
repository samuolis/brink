"""Use the supported Home Assistant test helpers across the pinned HA releases."""

from __future__ import annotations

from importlib.util import find_spec

if find_spec("pytest_homeassistant") is not None:
    from pytest_homeassistant.common import MockConfigEntry
else:
    from pytest_homeassistant_custom_component.common import MockConfigEntry

__all__ = ["MockConfigEntry"]
