"""Constant values for the Brink Home component."""

from __future__ import annotations

DOMAIN = "brink_ventilation"
MANUFACTURER = "Brink"
DEFAULT_MODEL = "Flair"

DEFAULT_SCAN_INTERVAL = 60
MIN_SCAN_INTERVAL = 45
REFRESH_DELAY = 2
EXPEDITED_INTERVAL = 15  # seconds — fixed fast poll rate, not user-configurable
EXPEDITED_DURATION = 180  # seconds (3 min) of fast polling after a write

# Options flow config keys
CONF_FREEZING_THRESHOLD = "freezing_threshold"
CONF_TEMPERATURE_SOURCE_ENTITY = "temperature_source_entity"
CONF_EXTRA_VENT_DURATION = "extra_vent_duration"
CONF_EXTRA_VENT_SUMMER_LEVEL = "extra_vent_summer_level"
CONF_EXTRA_VENT_WINTER_LEVEL = "extra_vent_winter_level"
CONF_AUTO_SUMMER_BASE_LEVEL = "auto_summer_base_level"
CONF_AUTO_WINTER_BASE_LEVEL = "auto_winter_base_level"
CONF_HUMIDITY_SENSOR_1 = "humidity_sensor_1"
CONF_HUMIDITY_SENSOR_2 = "humidity_sensor_2"
CONF_HUMIDITY_SENSOR_3 = "humidity_sensor_3"
CONF_HUMIDITY_SPIKE_THRESHOLD = "humidity_spike_threshold"
CONF_INDOOR_TEMPERATURE_ENTITY_1 = "indoor_temperature_entity_1"
CONF_INDOOR_TEMPERATURE_ENTITY_2 = "indoor_temperature_entity_2"

# Defaults for new options
DEFAULT_FREEZING_THRESHOLD = -2.0
DEFAULT_EXTRA_VENT_DURATION = 120  # minutes
DEFAULT_EXTRA_VENT_SUMMER_LEVEL = 3
DEFAULT_EXTRA_VENT_WINTER_LEVEL = 2
DEFAULT_AUTO_SUMMER_BASE_LEVEL = 2
DEFAULT_AUTO_WINTER_BASE_LEVEL = 1
DEFAULT_HUMIDITY_SPIKE_THRESHOLD = 1.5  # %/min

# Ranges
MAX_SCAN_INTERVAL = 300
MIN_FREEZING_THRESHOLD = -10.0
MAX_FREEZING_THRESHOLD = 10.0
MIN_EXTRA_VENT_DURATION = 15
MAX_EXTRA_VENT_DURATION = 480
MIN_HUMIDITY_SPIKE_THRESHOLD = 0.5  # %/min
MAX_HUMIDITY_SPIKE_THRESHOLD = 20.0  # %/min

# Season enum values
SEASON_SUMMER = "summer"
SEASON_WINTER = "winter"

# Boost trigger types
BOOST_TRIGGER_HUMIDITY = "humidity_spike"

# Logbook events
EVENT_BOOST_ACTIVATED = f"{DOMAIN}_boost_activated"
EVENT_BOOST_DEACTIVATED = f"{DOMAIN}_boost_deactivated"

# API endpoints
API_URL = "https://www.brink-home.com/portal/api/portal/"
API_V1_URL = "https://www.brink-home.com/portal/api/v1.1/"

# OIDC authentication
OIDC_AUTH_URL = "https://www.brink-home.com/idsrv/connect/authorize"
OIDC_TOKEN_URL = "https://www.brink-home.com/idsrv/connect/token"
OIDC_CLIENT_ID = "spa"
OIDC_REDIRECT_URI = "https://www.brink-home.com/app"
OIDC_SCOPE = "openid api role locale"

# Canonical parameter keys (matched by German API name, not numeric ID)
PARAM_DEVICE_TYPE = "device_type"
PARAM_SOFTWARE_LABEL = "software_label"
PARAM_FILTER_STATUS = "filter_status"
PARAM_DAYS_SINCE_FILTER_RESET = "days_since_filter_reset"
PARAM_ACTIVE_CONTROL_STATUS = "active_control_status"
PARAM_VENTILATION_LEVEL = "ventilation_level"
PARAM_OPERATING_MODE = "operating_mode"
PARAM_REMAINING_DURATION = "remaining_duration"
PARAM_SUPPLY_AIR_FLOW = "supply_air_flow"
PARAM_EXHAUST_AIR_FLOW = "exhaust_air_flow"
PARAM_EXHAUST_TEMP = "exhaust_temp"
PARAM_FRESH_AIR_TEMP = "fresh_air_temp"
PARAM_SUPPLY_TEMP = "supply_temp"
PARAM_BYPASS_VALVE_STATUS = "bypass_valve_status"
PARAM_PREHEATER_STATUS = "preheater_status"
PARAM_HUMIDITY = "humidity"
PARAM_CO2_SENSOR_1 = "co2_sensor_1"
PARAM_CO2_SENSOR_2 = "co2_sensor_2"
PARAM_CO2_SENSOR_3 = "co2_sensor_3"
PARAM_CO2_SENSOR_4 = "co2_sensor_4"
PARAM_BYPASS_OPERATION = "bypass_operation"

# German API name → canonical parameter key.
# Different Brink device models may use different numeric parameter IDs
# but the German firmware names are consistent across models.
PARAM_NAME_MAP: dict[str, str] = {
    "deviceTypeTitle": PARAM_DEVICE_TYPE,
    "softwareLabel": PARAM_SOFTWARE_LABEL,
    "Status Filtermeldung": PARAM_FILTER_STATUS,
    "Anzahl der Tage seit Filterreset": PARAM_DAYS_SINCE_FILTER_RESET,
    "Aktive Regelung": PARAM_ACTIVE_CONTROL_STATUS,
    "Lüftungsstufe": PARAM_VENTILATION_LEVEL,
    "Betriebsart": PARAM_OPERATING_MODE,
    "Restlaufzeit Betriebsartfunktion": PARAM_REMAINING_DURATION,
    "Ist-Wert Luftdurchsatz Zuluft": PARAM_SUPPLY_AIR_FLOW,
    "Ist-Wert Luftdurchsatz Abluft": PARAM_EXHAUST_AIR_FLOW,
    "Ablufttemperatur": PARAM_EXHAUST_TEMP,
    "Frischlufttemperatur": PARAM_FRESH_AIR_TEMP,
    "Zulufttemperatur": PARAM_SUPPLY_TEMP,
    "Status Bypassklappe": PARAM_BYPASS_VALVE_STATUS,
    "Status Vorheizregister": PARAM_PREHEATER_STATUS,
    "Relative Feuchte": PARAM_HUMIDITY,
    "PPM eBus CO2-sensor 1": PARAM_CO2_SENSOR_1,
    "PPM eBus CO2-sensor 2": PARAM_CO2_SENSOR_2,
    "PPM eBus CO2-sensor 3": PARAM_CO2_SENSOR_3,
    "PPM eBus CO2-sensor 4": PARAM_CO2_SENSOR_4,
    "Funktion der Bypass Klappe": PARAM_BYPASS_OPERATION,
}

# Value maps (API value -> translation key)
# Display labels are defined in translations/{lang}.json
ACTIVE_CONTROL_STATUS_MAP: dict[str, str] = {
    "0": "standby",
    "1": "bootloader",
    "2": "non_blocking_error",
    "3": "blocking_error",
    "4": "manual",
    "5": "holiday",
    "6": "night_ventilation",
    "7": "party",
    "8": "bypass_boost",
    "9": "normal_boost",
    "10": "auto_co2",
    "11": "auto_ebus",
    "12": "auto_modbus",
    "13": "auto_lan_wlan_portal",
    "14": "auto_lan_wlan_local",
}

BYPASS_OPEN_VALUE = "3"

BYPASS_VALVE_STATUS_MAP: dict[str, str] = {
    "0": "init",
    "1": "opening",
    "2": "closing",
    BYPASS_OPEN_VALUE: "open",
    "4": "closed",
}

PREHEATER_STATUS_MAP: dict[str, str] = {
    "0": "off",
    "1": "auto",
    "2": "lock_current",
    "3": "lock_maximum",
}

OPERATING_MODE_MAP: dict[str, str] = {
    "0": "automatic",
    "1": "manual",
    "2": "holiday",
    "3": "party",
    "4": "night",
}
OPERATING_MODE_REVERSE: dict[str, str] = {v: k for k, v in OPERATING_MODE_MAP.items()}

BYPASS_OPERATION_MAP: dict[str, str] = {
    "0": "automatic",
    "1": "bypass_closed",
    "2": "bypass_open",
}
BYPASS_OPERATION_REVERSE: dict[str, str] = {v: k for k, v in BYPASS_OPERATION_MAP.items()}

VENTILATION_LEVEL_MAP: dict[str, str] = {
    "0": "level_0",
    "1": "level_1",
    "2": "level_2",
    "3": "level_3",
    "4": "adaptive",
}
VENTILATION_LEVEL_REVERSE: dict[str, str] = {v: k for k, v in VENTILATION_LEVEL_MAP.items()}
