"""Definitions for Brink local UIDs."""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum, StrEnum


class ActiveControlStatus(IntEnum):
    """Brink active control status."""

    STANDBY = 0
    BOOTLOADER = 1
    NON_BLOCKING_ERROR = 2
    BLOCKING_ERROR = 3
    MANUAL = 4
    HOLIDAY = 5
    NIGHT_VENTILATION = 6
    PARTY = 7
    BYPASS_BOOST = 8
    NORMAL_BOOST = 9
    AUTO_CO2 = 10
    AUTO_EBUS = 11
    AUTO_MODBUS = 12
    AUTO_LAN_WLAN_PORTAL = 13
    AUTO_LAN_WLAN_LOCAL = 14


ACTIVE_CONTROL_STATUS_LABELS: dict[int, str] = {
    ActiveControlStatus.STANDBY: "Standby",
    ActiveControlStatus.BOOTLOADER: "Bootloader",
    ActiveControlStatus.NON_BLOCKING_ERROR: "Non-blocking error",
    ActiveControlStatus.BLOCKING_ERROR: "Blocking error",
    ActiveControlStatus.MANUAL: "Manual",
    ActiveControlStatus.HOLIDAY: "Holiday",
    ActiveControlStatus.NIGHT_VENTILATION: "Night ventilation",
    ActiveControlStatus.PARTY: "Party",
    ActiveControlStatus.BYPASS_BOOST: "Bypass boost",
    ActiveControlStatus.NORMAL_BOOST: "Normal boost",
    ActiveControlStatus.AUTO_CO2: "Automatic CO₂",
    ActiveControlStatus.AUTO_EBUS: "Automatic eBus",
    ActiveControlStatus.AUTO_MODBUS: "Automatic Modbus",
    ActiveControlStatus.AUTO_LAN_WLAN_PORTAL: "Automatic LAN/WLAN Portal",
    ActiveControlStatus.AUTO_LAN_WLAN_LOCAL: "Automatic LAN/WLAN Local",
}


class UIDType(StrEnum):
    """Supported UID value types."""

    BOOL = "bool"
    INT = "int"
    FLOAT = "float"
    ENUM = "enum"
    UINT16 = "uint16"
    UINT32 = "uint32"
    TEMPERATURE = "temperature"
    HUMIDITY = "humidity"
    PRESSURE = "pressure"
    AIRFLOW = "airflow"
    RPM = "rpm"
    ASCII = "ascii"
    IP_ADDRESS = "ip_address"
    VERSION = "version"
    DATE = "date"
    TIME = "time"


class UIDUnit(StrEnum):
    """Supported engineering units."""
    CELSIUS = "°C"
    PERCENT = "%"
    PASCAL = "Pa"
    CUBIC_METERS_PER_HOUR = "m³/h"
    RPM = "RPM"


class UIDAccess(StrEnum):
    """Supported access modes."""

    READ = "read"
    WRITE = "write"
    READ_WRITE = "read_write"


@dataclass(frozen=True, slots=True, kw_only=True)
class UIDDefinition:
    """Describe a Brink local UID."""

    uid: int
    key: str
    value_type: UIDType
    scale: int = 1
    unit: UIDUnit | None = None
    enum_type: type | None = None
    writable: bool = False
    description: str | None = None
    available_since: tuple[int, int] | None = None
    access: UIDAccess = UIDAccess.READ


UID_DEFINITIONS: tuple[UIDDefinition, ...] = (
    #
    # Operating state
    #
    UIDDefinition(
        uid=0,
        key="base_firmware_descriptor",
        value_type=UIDType.ASCII,
        description="base firmware descriptor",
    ),
    UIDDefinition(
        uid=1,
        key="ventilation_mode",
        value_type=UIDType.INT,
        description="Current ventilation mode",
    ),
    UIDDefinition(
        uid=2,
        key="supply_fan_rpm",
        value_type=UIDType.RPM,
        unit=UIDUnit.RPM,
        description="Supply fan speed",
    ),
    UIDDefinition(
        uid=3,
        key="exhaust_fan_rpm",
        value_type=UIDType.RPM,
        unit=UIDUnit.RPM,
        description="Exhaust fan speed",
    ),
    UIDDefinition(
        uid=6,
        key="outside_temperature",
        value_type=UIDType.TEMPERATURE,
        unit=UIDUnit.CELSIUS,
        scale=10,
    ),
    UIDDefinition(
        uid=8,
        key="supply_airflow",
        value_type=UIDType.AIRFLOW,
        unit=UIDUnit.CUBIC_METERS_PER_HOUR,
        description="Current supply airflow",
    ),
    UIDDefinition(
        uid=9,
        key="exhaust_airflow",
        value_type=UIDType.AIRFLOW,
        unit=UIDUnit.CUBIC_METERS_PER_HOUR,
        description="Current exhaust airflow",
    ),
    UIDDefinition(
        uid=10,
        key="supply_airflow_setpoint",
        value_type=UIDType.AIRFLOW,
        unit=UIDUnit.CUBIC_METERS_PER_HOUR,
        description="Current supply airflow setpoint",
    ),
    UIDDefinition(
        uid=11,
        key="exhaust_airflow_setpoint",
        value_type=UIDType.AIRFLOW,
        unit=UIDUnit.CUBIC_METERS_PER_HOUR,
        description="Current exhaust airflow setpoint",
    ),
    UIDDefinition(
        uid=19,
        key="supply_pressure",
        value_type=UIDType.PRESSURE,
        unit=UIDUnit.PASCAL,
        description="Supply duct pressure",
    ),
    UIDDefinition(
        uid=20,
        key="exhaust_pressure",
        value_type=UIDType.PRESSURE,
        unit=UIDUnit.PASCAL,
        description="Exhaust duct pressure",
    ),
    UIDDefinition(
        uid=22,
        key="bypass_open",
        value_type=UIDType.BOOL,
        description="Bypass valve open",
    ),
    UIDDefinition(
        uid=23,
        key="frost_protection",
        value_type=UIDType.BOOL,
        description="Frost protection active",
    ),
    UIDDefinition(
        uid=35,
        key="operating_mode",
        value_type=UIDType.ENUM,
        enum_type=ActiveControlStatus,
        description="Operating mode",
    ),
    UIDDefinition(
        uid=44,
        key="active_control_status",
        value_type=UIDType.ENUM,
        enum_type=ActiveControlStatus,
        description="Active control status",
    ),
    UIDDefinition(
        uid=45,
        key="days_since_filter_reset?",
        value_type=UIDType.UINT32,
        description="Days since filter reset",
    ),
    UIDDefinition(
        uid=46,
        key="unknown_46",
        value_type=UIDType.UINT32,
        description="Unknown raw supply fan value",
    ),
    UIDDefinition(
        uid=47,
        key="unknown_47",
        value_type=UIDType.UINT32,
        description="Unknown raw exhaust fan value",
    ),
    UIDDefinition(
        uid=49,
        key="dipswitch",
        value_type=UIDType.INT,
        description="DIP switch value",
    ),
    UIDDefinition(
        uid=51,
        key="supply_temperature",
        value_type=UIDType.TEMPERATURE,
        unit=UIDUnit.CELSIUS,
        scale=10,
        description="Supply temperature",
    ),
    UIDDefinition(
        uid=52,
        key="supply_humidity",
        value_type=UIDType.HUMIDITY,
        unit=UIDUnit.PERCENT,
        description="Supply air relative humidity",
        scale=1,
    ),
    UIDDefinition(
        uid=53,
        key="exhaust_temperature",
        value_type=UIDType.TEMPERATURE,
        unit=UIDUnit.CELSIUS,
        scale=10,
        description="Exhaust temperature",
    ),
    UIDDefinition(
        uid=54,
        key="exhaust_humidity",
        value_type=UIDType.HUMIDITY,
        unit=UIDUnit.PERCENT,
        description="Extract air relative humidity",
    ),
    UIDDefinition(
        uid=70,
        key="base_firmware_version",
        value_type=UIDType.ASCII,
        description="Base firmware version",
    ),
    UIDDefinition(
        uid=73,
        key="uif_firmware_version",
        value_type=UIDType.ASCII,
        description="UIF firmware version",
    ),
    UIDDefinition(
        uid=78,
        key="webserver_version",
        value_type=UIDType.ASCII,
        description="Web server version",
    ),
    UIDDefinition(
        uid=83,
        key="device_time",
        value_type=UIDType.TIME,
        description="Time on the device",
    ),
    UIDDefinition(
        uid=84,
        key="device_date",
        value_type=UIDType.DATE,
        description="Date on the device",
    ),
    #
    # Network
    #
    UIDDefinition(
        uid=91,
        key="ip_address",
        value_type=UIDType.IP_ADDRESS,
    ),
    UIDDefinition(
        uid=16049,
        key="preheater_power",
        value_type=UIDType.INT,
        available_since=(3, 1),
    ),
    UIDDefinition(
        uid=60000,
        key="default_gateway",
        value_type=UIDType.IP_ADDRESS,
    ),
    UIDDefinition(
        uid=60001,
        key="subnet_mask",
        value_type=UIDType.IP_ADDRESS,
    ),
    UIDDefinition(
        uid=60002,
        key="primary_dns",
        value_type=UIDType.IP_ADDRESS,
    ),
    UIDDefinition(
        uid=60003,
        key="secondary_dns",
        value_type=UIDType.IP_ADDRESS,
    ),
    UIDDefinition(
        uid=60004,
        key="module_name",
        value_type=UIDType.ASCII,
        description="Configured Home Module name",
    ),
    UIDDefinition(
        uid=60005,
        key="destination_server",
        value_type=UIDType.ASCII,
        description="Configured Brink cloud server hostname",
    ),
    UIDDefinition(
        uid=60006,
        key="destination_port",
        value_type=UIDType.UINT16,
    ),
    UIDDefinition(
        uid=60008,
        key="wifi_name",
        value_type=UIDType.ASCII,
        description="WiFi name",
    ),
    UIDDefinition(
        uid=60031,
        key="wifi_ssid",
        value_type=UIDType.ASCII,
        description="Configured Wi-Fi SSID",
    ),
)

UID_LOOKUP: dict[int, UIDDefinition] = {
    definition.uid: definition
    for definition in UID_DEFINITIONS
}


def parse_ascii(values: list[int]) -> str:
    """Parse a null-terminated ASCII string."""
    return bytes(value for value in values).split(b"\x00", 1)[0].decode("ascii")


def parse_base_version(values: list[int]) -> str:
    """Parse the base firmware version."""

    if len(values) < 4:
        return ""

    prefix = chr(values[0])
    return f"{prefix}{values[1]}.{values[2]:02}.{values[3]:02}"
