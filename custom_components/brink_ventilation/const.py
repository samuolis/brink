"""Constant values for the Brink Home component."""

from __future__ import annotations

DOMAIN = "brink_ventilation"
DEFAULT_NAME = "Brink"
DEFAULT_MODEL = "Brink ventilation"

DATA_CLIENT = "brink_client"
DATA_COORDINATOR = "coordinator"

DEFAULT_SCAN_INTERVAL = 30

API_V1_URL = "https://www.brink-home.com/portal/api/v1.1/"

OIDC_AUTH_URL = "https://www.brink-home.com/idsrv/connect/authorize"
OIDC_TOKEN_URL = "https://www.brink-home.com/idsrv/connect/token"
OIDC_CLIENT_ID = "spa"
OIDC_REDIRECT_URI = "https://www.brink-home.com/app/"
OIDC_SCOPE = "openid api role locale"

PARAM_DEVICE_TYPE = "device_type"
PARAM_SOFTWARE_LABEL = "software_label"
PARAM_VENTILATION_LEVEL = "ventilation_level"
PARAM_OPERATING_MODE = "operating_mode"
PARAM_FILTER_STATUS = "filter_status"
PARAM_REMAINING_DURATION = "remaining_duration"
PARAM_ACTIVE_CONTROL_STATUS = "active_control_status"
PARAM_SUPPLY_AIR_FLOW = "supply_air_flow"
PARAM_EXHAUST_AIR_FLOW = "exhaust_air_flow"
PARAM_EXHAUST_TEMP = "exhaust_temp"
PARAM_FRESH_AIR_TEMP = "fresh_air_temp"
PARAM_SUPPLY_TEMP = "supply_temp"
PARAM_HUMIDITY = "humidity"
PARAM_PREHEATER_STATUS = "preheater_status"
PARAM_BYPASS_VALVE_STATUS = "bypass_valve_status"
PARAM_BYPASS_OPERATION = "bypass_operation"
PARAM_CO2_SENSOR_1 = "co2_sensor_1"
PARAM_CO2_SENSOR_2 = "co2_sensor_2"
PARAM_CO2_SENSOR_3 = "co2_sensor_3"
PARAM_CO2_SENSOR_4 = "co2_sensor_4"
PARAM_DAYS_SINCE_FILTER_RESET = "days_since_filter_reset"

PARAM_NAME_MAP: dict[str, str] = {
    "deviceTypeTitle": PARAM_DEVICE_TYPE,
    "softwareLabel": PARAM_SOFTWARE_LABEL,
    "Lüftungsstufe": PARAM_VENTILATION_LEVEL,
    "Betriebsart": PARAM_OPERATING_MODE,
    "Status Filtermeldung": PARAM_FILTER_STATUS,
    "Restlaufzeit Betriebsartfunktion": PARAM_REMAINING_DURATION,
    "Aktive Regelung": PARAM_ACTIVE_CONTROL_STATUS,
    "Ist-Wert Luftdurchsatz Zuluft": PARAM_SUPPLY_AIR_FLOW,
    "Ist-Wert Luftdurchsatz Abluft": PARAM_EXHAUST_AIR_FLOW,
    "Ablufttemperatur": PARAM_EXHAUST_TEMP,
    "Frischlufttemperatur": PARAM_FRESH_AIR_TEMP,
    "Zulufttemperatur": PARAM_SUPPLY_TEMP,
    "Relative Feuchte": PARAM_HUMIDITY,
    "Status Vorheizregister": PARAM_PREHEATER_STATUS,
    "Status Bypassklappe": PARAM_BYPASS_VALVE_STATUS,
    "Funktion der Bypass Klappe": PARAM_BYPASS_OPERATION,
    "PPM eBus CO2-sensor 1": PARAM_CO2_SENSOR_1,
    "PPM eBus CO2-sensor 2": PARAM_CO2_SENSOR_2,
    "PPM eBus CO2-sensor 3": PARAM_CO2_SENSOR_3,
    "PPM eBus CO2-sensor 4": PARAM_CO2_SENSOR_4,
    "Anzahl der Tage seit Filterreset": PARAM_DAYS_SINCE_FILTER_RESET,
}

ACTIVE_CONTROL_STATUS_LABELS: dict[str, str] = {
    "0": "Standby",
    "1": "Bootloader",
    "2": "Non-blocking Error",
    "3": "Blocking Error",
    "4": "Manual",
    "5": "Holiday",
    "6": "Night Ventilation",
    "7": "Party",
    "8": "Bypass Boost",
    "9": "Normal Boost",
    "10": "Auto CO2",
    "11": "Auto eBus",
    "12": "Auto Modbus",
    "13": "Auto LAN/WLAN Portal",
    "14": "Auto LAN/WLAN Local",
}

BYPASS_OPERATION_LABELS: dict[str, str] = {
    "0": "Automatic",
    "1": "Bypass Closed",
    "2": "Bypass Open",
}

# gatewayState enum from the Brink web app.
GATEWAY_STATE_LOCKED = 0
GATEWAY_STATE_OFFLINE = 1
GATEWAY_STATE_ONLINE = 2

GATEWAY_STATE_LABELS: dict[int, str] = {
    GATEWAY_STATE_LOCKED: "locked",
    GATEWAY_STATE_OFFLINE: "offline",
    GATEWAY_STATE_ONLINE: "online",
}

MODE_MANUAL_VALUE = "1"
WRITE_VALUE_STATE = 0
