"""Constant values for the Brink Home component."""

from __future__ import annotations

DOMAIN = "brink_ventilation"
MANUFACTURER = "Brink"
DEFAULT_MODEL = "Flair"

DEFAULT_SCAN_INTERVAL = 60
MIN_SCAN_INTERVAL = 15
REFRESH_DELAY = 2
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
DEFAULT_HUMIDITY_SPIKE_THRESHOLD = 2.0  # %/min

# Ranges
MAX_SCAN_INTERVAL = 300
MIN_FREEZING_THRESHOLD = -10.0
MAX_FREEZING_THRESHOLD = 10.0
MIN_EXTRA_VENT_DURATION = 15
MAX_EXTRA_VENT_DURATION = 480
MIN_HUMIDITY_SPIKE_THRESHOLD = 0.5  # %/min
MAX_HUMIDITY_SPIKE_THRESHOLD = 20.0  # %/min

# Humidity monitoring
HUMIDITY_WINDOW_SECONDS = 180  # 3 minutes of rolling history
HUMIDITY_MIN_SAMPLE_INTERVAL = 30  # seconds between samples

# Season enum values
SEASON_SUMMER = "summer"
SEASON_WINTER = "winter"

# API endpoints
API_URL = "https://www.brink-home.com/portal/api/portal/"
API_V1_URL = "https://www.brink-home.com/portal/api/v1.1/"

# OIDC authentication
OIDC_AUTH_URL = "https://www.brink-home.com/idsrv/connect/authorize"
OIDC_TOKEN_URL = "https://www.brink-home.com/idsrv/connect/token"
OIDC_CLIENT_ID = "spa"
OIDC_REDIRECT_URI = "https://www.brink-home.com/app"
OIDC_SCOPE = "openid api role locale"

# Parameter IDs
PARAM_DEVICE_TYPE = 17000
PARAM_SOFTWARE_LABEL = 17002
PARAM_FILTER_STATUS = 17006
PARAM_DAYS_SINCE_FILTER_RESET = 17007
PARAM_ACTIVE_CONTROL_STATUS = 17009
PARAM_VENTILATION_LEVEL = 17011
PARAM_OPERATING_MODE = 17012
PARAM_REMAINING_DURATION = 17013
PARAM_SUPPLY_AIR_FLOW = 17015
PARAM_EXHAUST_AIR_FLOW = 17017
PARAM_FRESH_AIR_TEMP = 17019
PARAM_SUPPLY_TEMP = 17020
PARAM_BYPASS_VALVE_STATUS = 17024
PARAM_PREHEATER_STATUS = 17025
PARAM_HUMIDITY = 17026
PARAM_CO2_SENSOR_1 = 17027
PARAM_CO2_SENSOR_2 = 17028
PARAM_CO2_SENSOR_3 = 17029
PARAM_CO2_SENSOR_4 = 17030
PARAM_BYPASS_OPERATION = 17143

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

BYPASS_VALVE_STATUS_MAP: dict[str, str] = {
    "0": "init",
    "1": "opening",
    "2": "closing",
    "3": "open",
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
