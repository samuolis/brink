from dataclasses import dataclass
from typing import Final

REFERENCE_MAX_AIRFLOW: Final[float] = 300.0
REFERENCE_MAX_PRESSURE: Final[float] = 100.0


@dataclass(frozen=True, slots=True)
class SoundPowerCoefficients:
    """Sound power regression coefficients."""

    constant: float
    airflow: float
    pressure: float
    airflow_pressure: float
    airflow_squared: float
    pressure_squared: float


CABINET_SOUND_POWER_COEFFICIENTS = SoundPowerCoefficients(
    constant=0.0,
    airflow=0.395520111,
    pressure=-0.343800277,
    airflow_pressure=0.003548405,
    airflow_squared=-0.001255201,
    pressure_squared=-0.002876006,
)

SUPPLY_SOUND_POWER_COEFFICIENTS = SoundPowerCoefficients(
    constant=0.0,
    airflow=0.632995839,
    pressure=-0.747489598,
    airflow_pressure=0.006001479,
    airflow_squared=-0.002096625,
    pressure_squared=-0.004149792,
)

EXHAUST_SOUND_POWER_COEFFICIENTS = SoundPowerCoefficients(
    constant=0.0,
    airflow=0.449778086,
    pressure=-0.379445215,
    airflow_pressure=0.003256681,
    airflow_squared=-0.001264448,
    pressure_squared=-0.002788904,
)


def estimate_sound_power(
    airflow: float,
    pressure: float,
    coefficients: SoundPowerCoefficients,
) -> float:
    """Estimate the sound power level in dB(A).

    The estimate is based on a second-order polynomial regression fitted to
    Brink reference measurements.
    The input values are clamped to the supported operating range of the
    Brink reference measurements.

    Args:
        airflow: Airflow in m³/h.
        pressure: Static pressure in Pa.
        coefficients: Polynomial regression coefficients.

    Returns:
        Estimated sound power in dB(A).
    """

    if airflow <= 0.0:
        return 0.0

    airflow = _clamp(airflow, 0.0, REFERENCE_MAX_AIRFLOW)
    pressure = _clamp(pressure, 0.0, REFERENCE_MAX_PRESSURE)

    sound_power = (
        coefficients.constant
        + coefficients.airflow * airflow
        + coefficients.pressure * pressure
        + coefficients.airflow_pressure * airflow * pressure
        + coefficients.airflow_squared * airflow**2
        + coefficients.pressure_squared * pressure**2
    )

    return max(sound_power, 0.0)


def _clamp(
    value: float,
    minimum: float,
    maximum: float,
) -> float:
    """Clamp a value to the specified range."""
    return max(minimum, min(maximum, value))
