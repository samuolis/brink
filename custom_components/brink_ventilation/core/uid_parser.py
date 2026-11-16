"""Parser for Brink local UID values."""

from __future__ import annotations

from collections.abc import Callable

from .uid_definitions import UID_LOOKUP, UIDType


def _parse_bytes(value: str) -> list[int]:
    """Parse a comma-separated byte string."""
    return [int(part.strip()) for part in value.split(",")]


def parse_uint16(values: list[int]) -> int:
    """Parse a little-endian unsigned 16-bit integer."""
    if len(values) < 2:
        raise ValueError("Expected at least two bytes.")

    if any(byte < 0 or byte > 255 for byte in values[:2]):
        raise ValueError("Bytes must be in range 0..255.")

    return values[0] | (values[1] << 8)


def decode_uint16(value: str) -> int:
    """Decode a little-endian unsigned 16-bit integer."""
    return parse_uint16(_parse_bytes(value))


def decode_uint32(value: str) -> int:
    """Decode a little-endian unsigned 32-bit integer."""
    bytes_list = _parse_bytes(value)
    if len(bytes_list) < 4:
        raise ValueError("Expected at least four bytes.")

    if any(byte < 0 or byte > 255 for byte in bytes_list[:4]):
        raise ValueError("Bytes must be in range 0..255.")

    return (
        bytes_list[0]
        | (bytes_list[1] << 8)
        | (bytes_list[2] << 16)
        | (bytes_list[3] << 24)
    )


def decode_bool(value: str) -> bool:
    """Decode a boolean value."""
    return decode_uint16(value) != 0


def decode_percent(value: str) -> int:
    """Decode a percentage."""
    return decode_uint16(value)


def decode_rpm(value: str) -> int:
    """Decode a fan speed."""
    return decode_uint16(value)


def decode_airflow(value: str) -> int:
    """Decode airflow in m³/h."""
    return decode_uint16(value)


def decode_temperature(value: str) -> float:
    """Decode a temperature.

    Brink stores temperatures as tenths of a degree.
    Example:
        "231,0" -> 23.1
    """
    return decode_uint16(value) / 10.0


def decode_humidity(value: str) -> int:
    """Decode relative humidity."""
    return decode_uint16(value)


def decode_pressure(value: str) -> int:
    """Decode pressure in Pa."""
    return decode_uint16(value)


def decode_ip_address(value: str) -> str:
    """Decode an IP address."""
    bytes_list = _parse_bytes(value)
    if len(bytes_list) != 4:
        raise ValueError("Expected exactly four bytes for an IP address.")
    return ".".join(str(byte) for byte in bytes_list)


def decode_version(value: str) -> str:
    """Decode a version string."""
    bytes_list = _parse_bytes(value)
    if len(bytes_list) < 4:
        raise ValueError("Expected at least four bytes for a version string.")
    prefix = chr(bytes_list[0])
    return f"{prefix}{bytes_list[1]}.{bytes_list[2]:02}.{bytes_list[3]:02}"


def decode_ascii(value: str) -> str:
    """Decode a null-terminated ASCII string."""
    return (
        bytes(number for number in _parse_bytes(value) if number)
        .decode("ascii", errors="strict")
    )


def decode_time(value: str) -> str:
    """Decode a device time."""
    bytes_list = _parse_bytes(value)

    if len(bytes_list) < 2:
        raise ValueError("Expected at least two bytes for a time.")

    return f"{bytes_list[0]:02d}:{bytes_list[1]:02d}"


def decode_date(value: str) -> str:
    """Decode a date in YYYY-MM-DD format."""
    bytes_list = _parse_bytes(value)
    if len(bytes_list) < 3:
        raise ValueError("Expected at least three bytes for a date.")
    day = bytes_list[0]
    month = bytes_list[1]
    year = 2000 + bytes_list[2]
    return f"{year:04d}-{month:02d}-{day:02d}"


DECODERS: dict[UIDType, Callable[[str], object]] = {
    UIDType.UINT16: decode_uint16,
    UIDType.UINT32: decode_uint32,
    UIDType.BOOL: decode_bool,
    UIDType.INT: decode_uint16,
    UIDType.RPM: decode_rpm,
    UIDType.AIRFLOW: decode_airflow,
    UIDType.PRESSURE: decode_pressure,
    UIDType.TEMPERATURE: decode_temperature,
    UIDType.HUMIDITY: decode_humidity,
    UIDType.ASCII: decode_ascii,
    UIDType.IP_ADDRESS: decode_ip_address,
    UIDType.VERSION: decode_version,
    UIDType.TIME: decode_time,
    UIDType.DATE: decode_date,
}


def parse_uid_values(
    values: dict[str, str],
) -> dict[str, object]:
    """Convert raw UID values into named values."""
    parsed: dict[str, object] = {}

    for uid_key, raw_value in values.items():
        uid = int(uid_key.removeprefix("UID"))

        definition = UID_LOOKUP.get(uid)
        if definition is None:
            continue

        decoder = DECODERS.get(definition.value_type)
        if decoder is None:
            parsed[definition.key] = raw_value
            continue

        try:
            parsed[definition.key] = decoder(raw_value)
        except (TypeError, ValueError):
            parsed[definition.key] = raw_value

    return parsed
