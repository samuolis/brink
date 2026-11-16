from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import IntEnum, IntFlag, StrEnum
from math import hypot, isclose
from typing import TypedDict

_EPSILON = 1e-9


class BrinkSystem(TypedDict):
    """Describe a portal system whose optional alert summary may be absent."""

    system_id: int
    name: str
    serial_number: str | None
    gateway_state: str | None
    is_system_owner: bool
    is_editable: bool
    access_level: int
    owner_group_name: str | None
    is_favorite: bool
    active_alert_count: int | None
    iana_time_zone: str
    two_letter_country_code: str
    user_group_names: list[str]
    total_count: int


@dataclass(slots=True, frozen=True)
class BrinkDeviceData:
    """Brink device data."""
    api_is_online: bool
    system_id: int

    # User-configurable device name.
    name: str  # API/internal name, e.g. Flair1214_11

    # Immutable internal Brink device identifier.
    internal_name: str | None  # Flair1214_11

    # Marketing/product model.
    model: str  # Flair 300

    serial_number: str | None
    gateway_state: str | None
    gateway_type_id: int | None
    device_is_online: bool
    ip_address: str | None
    dns_server: str | None
    sw_version: str | None
    alerts: list[BrinkAlert]
    parameters: dict[str, dict[str, object]]
    has_blocking_error: bool = False
    is_system_owner: bool | None = None
    is_editable: bool | None = None
    access_level: int | None = None
    owner_group_name: str | None = None
    is_favorite: bool | None = None
    active_alert_count: int | None = None
    iana_time_zone: str | None = None
    two_letter_country_code: str | None = None
    user_group_names: list[str] | None = None
    total_count: int | None = None


@dataclass(slots=True, frozen=True)
class BrinkAlert:
    """Brink alert."""

    id: int
    component_id: int
    code: int
    level: BrinkAlertLevel
    is_active: bool
    is_archived: bool
    incoming: datetime
    outgoing: datetime | None
    code_text: str | None
    description: str | None


class BrinkAlertLevel(IntEnum):
    """Brink alert severity level."""

    INFORMATION = 0
    WARNING = 1
    ERROR = 2
    BLOCKING = 3


@dataclass(slots=True, frozen=True)
class BrinkUser:
    """Brink user."""

    username: str
    culture_info_code: str
    user_role_id: int
    mail_address_id: int


class BrinkUserRole(IntEnum):
    """Brink user role."""

    END_USER = 1
    END_USER_PLUS = 2
    EXPERT = 3
    OEM = 4


class BrinkAccessLevel(IntFlag):
    """Brink system access level."""

    USER_READ = 0x0004
    USER_WRITE = 0x0008

    EXPERT_READ = 0x0100
    EXPERT_WRITE = 0x0200

    MANUFACTURER_READ = 0x4000
    MANUFACTURER_WRITE = 0x8000


@dataclass(slots=True, frozen=True)
class BrinkSettingValue:
    """Brink setting value."""

    value: int
    translation_id: str


@dataclass(slots=True, frozen=True)
class BrinkSettings:
    """Brink portal settings."""

    access_levels: list[BrinkSettingValue]
    user_roles: list[BrinkSettingValue]
    receiver_periods: list[BrinkSettingValue]


@dataclass(slots=True, frozen=True)
class SoundPowerPoint:
    """Reference sound power measurement."""

    airflow: float
    pressure: float
    cabinet: float
    exhaust: float
    supply: float

    def sound_power(
        self,
        channel: SoundChannel,
    ) -> float:
        """Return the sound power for the requested channel."""
        return {
            SoundChannel.CABINET: self.cabinet,
            SoundChannel.EXHAUST: self.exhaust,
            SoundChannel.SUPPLY: self.supply,
        }[channel]


SOUND_POWER_POINTS = (
    # airflow, pressure, cabinet, exhaust, supply
    SoundPowerPoint(0.0, 0.0, 0.0, 0.0, 0.0),
    SoundPowerPoint(150.0, 25.0, 34.0, 40.0, 49.0),
    SoundPowerPoint(200.0, 50.0, 40.0, 46.0, 55.0),
    SoundPowerPoint(228.0, 50.0, 41.0, 48.0, 56.0),
    SoundPowerPoint(250.0, 100.0, 46.0, 49.0, 61.0),
    SoundPowerPoint(300.0, 100.0, 49.0, 53.0, 65.0),
)


class SoundChannel(StrEnum):
    """Sound power channel."""

    CABINET = "cabinet"
    EXHAUST = "exhaust"
    SUPPLY = "supply"


def interpolate_sound_power(
    airflow: float,
    pressure: float,
    channel: SoundChannel,
) -> float:
    """Estimate the sound power using 2D inverse distance weighting.

    The estimation is based on the Brink reference measurements for
    airflow (m³/h) and static pressure (Pa).

    Args:
        airflow: Airflow in m³/h.
        pressure: Static pressure in Pa.
        channel: Sound power channel to estimate.

    Returns:
        Estimated sound power in dB(A).
    """
    if airflow <= 0.0:
        return 0.0

    airflow = min(max(airflow, 0.0), 300.0)
    pressure = min(max(pressure, 0.0), 100.0)

    weighted_sum = 0.0
    total_weight = 0.0

    for point in SOUND_POWER_POINTS:
        distance = hypot(
            airflow - point.airflow,
            pressure - point.pressure,
        )

        if isclose(distance, 0.0, abs_tol=_EPSILON):
            return point.sound_power(channel)

        weight = 1.0 / (distance * distance)

        weighted_sum += weight * point.sound_power(channel)
        total_weight += weight

    if isclose(total_weight, 0.0, abs_tol=_EPSILON):
        return 0.0

    return round(weighted_sum / total_weight, 1)
