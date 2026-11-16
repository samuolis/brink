"""Constant values for the Brink Home component."""

from __future__ import annotations

from dataclasses import dataclass

DOMAIN = "brink_ventilation"
DEFAULT_NAME = "Brink"
DEFAULT_MODEL = "Brink ventilation"

DATA_CLIENT = "brink_client"
DATA_COORDINATOR = "coordinator"

DEFAULT_SCAN_INTERVAL = 30

API_BASE = "https://www.brink-home.com"
API_V1_URL = f"{API_BASE}/portal/api/v1.1/"

ALERTS_URL = (
    f"{API_V1_URL}/systems/{{system_id}}/alerts/criterion"
    "?pageIndex=0"
    "&pageSize=10"
    "&sortColumn=level"
    "&sortDirection=2"
    "&filterSpecs%5B0%5D.fieldName=isArchived"
    "&filterSpecs%5B0%5D.value=false"
)

OIDC_AUTH_URL = f"{API_BASE}/idsrv/connect/authorize"
OIDC_TOKEN_URL = f"{API_BASE}/idsrv/connect/token"
OIDC_CLIENT_ID = "spa"
OIDC_REDIRECT_URI = f"{API_BASE}/app/"
OIDC_SCOPE = "openid api role locale"

MODE_AUTOMATIC = "automatic"
MODE_MANUAL = "manual"
MODE_HOLIDAY = "holiday"
MODE_PARTY = "party"
MODE_NIGHT = "night_ventilation"

ACCESS_LEVEL_MAP: dict[int, str] = {
    4: "User (Read)",
    12: "User (Read/Write)",
    16: "User+ (Read)",
    48: "User+ (Read/Write)",
    256: "Expert (Read)",
    768: "Expert (Read/Write)",
    16384: "Manufacturer (Read)",
    49152: "Manufacturer (Read/Write)",
}

ALERTS_URL_PARAMS = {
    "pageIndex": 0,
    "pageSize": 10,
    "sortColumn": "level",
    "sortDirection": 2,
    "filterSpecs[0].fieldName": "isArchived",
    "filterSpecs[0].value": "false",
}

ACCESS_LEVELS_FOR_SYSTEM_SHARE: dict[int, str] = {
    4: "accessLevelUserRead",
    12: "accessLevelUserReadWrite",
    16: "accessLevelUserPlusRead",
    48: "accessLevelUserPlusReadWrite",
    256: "accessLevelExpertRead",
    768: "accessLevelExpertReadWrite",
    16384: "accessLevelManufacturerRead",
    49152: "accessLevelManufacturerReadWrite",
}

LEVEL_LABELS = {
    0: "off",
    1: "low",
    2: "medium",
    3: "high",
    4: "CN1",
}

VENTILATION_LEVEL_LABELS = {
    0: "Off",
    1: "Low",
    2: "Medium",
    3: "High",
    4: "CN1",
}

# when changing gateway password within brink device the portal will be in locked state untill you (re)logged in to the portal again.
GATEWAY_STATE_LABELS: dict[int, str] = {
    0: "locked",
    1: "offline",
    2: "online",
}

GATEWAY_STATE_MAP = {
    0: "locked",
    1: "offline",
    2: "online",
}

GATEWAY_TYPE_LABELS = {
    3: "Brink Home Gateway",
}

VALUE_STATE_VALID = 0
VALUE_STATE_CONFIG = 1
VALUE_STATE_NO_DATA = 5

VALUE_STATE_MAP: dict[int, str] = {
    VALUE_STATE_VALID: "valid",
    VALUE_STATE_CONFIG: "config",
    VALUE_STATE_NO_DATA: "no_data",
}

CONTROL_TYPE_ENUM = 0
CONTROL_TYPE_NUMERIC = 6
CONTROL_TYPE_TEXT = 9

CONTROL_TYPE_MAP: dict[int, str] = {
    CONTROL_TYPE_ENUM: "enum",
    CONTROL_TYPE_NUMERIC: "numeric",
    CONTROL_TYPE_TEXT: "text",
}

PARAM_DEVICE_TYPE = "device_type"
PARAM_SOFTWARE_LABEL = "software_label"
PARAM_VENTILATION_LEVEL = "ventilation_level"
PARAM_OPERATING_MODE = "operating_mode"
PARAM_FILTER_STATUS = "filter_status"
PARAM_REMAINING_DURATION = "remaining_duration"
PARAM_ACTIVE_CONTROL_STATUS = "active_control_status"
PARAM_SUPPLY_AIR_FLOW = "actual_supply_air_flow"
PARAM_ACTUAL_SUPPLY_AIR_FLOW = "actual_supply_air_flow"
PARAM_ACTUAL_EXHAUST_AIR_FLOW = "actual_exhaust_air_flow"
PARAM_EXHAUST_AIR_FLOW = "actual_exhaust_air_flow"
PARAM_NOMINAL_SUPPLY_AIR_FLOW = "nominal_supply_air_flow"
PARAM_NOMINAL_EXHAUST_AIR_FLOW = "nominal_exhaust_air_flow"
PARAM_EXHAUST_TEMP = "exhaust_temp"
PARAM_FRESH_AIR_TEMP = "fresh_air_temp"
PARAM_SUPPLY_TEMP = "supply_temp"
PARAM_SUPPLY_AIR_PRESSURE = "supply_air_pressure"
PARAM_EXHAUST_AIR_PRESSURE = "exhaust_air_pressure"
PARAM_HUMIDITY = "humidity"
PARAM_PREHEATER_POWER = "preheater_power"
PARAM_PREHEATER_STATUS = "preheater_status"
PARAM_BYPASS_VALVE_STATUS = "bypass_valve_status"
PARAM_BYPASS_OPERATION = "bypass_operation"
PARAM_CO2_SENSOR_1 = "co2_sensor_1"
PARAM_CO2_SENSOR_2 = "co2_sensor_2"
PARAM_CO2_SENSOR_3 = "co2_sensor_3"
PARAM_CO2_SENSOR_4 = "co2_sensor_4"
PARAM_DAYS_SINCE_FILTER_RESET = "days_since_filter_reset"
PARAM_VENTILATION_MODE_0 = "ventilation_mode_0_airflow"
PARAM_VENTILATION_MODE_1 = "ventilation_mode_1_airflow"
PARAM_VENTILATION_MODE_2 = "ventilation_mode_2_airflow"
PARAM_VENTILATION_MODE_3 = "ventilation_mode_3_airflow"
PARAM_FROST_PROTECTION_STATUS = "frost_protection_status"
PARAM_STATUS_GEOTHERMAL_HEAT_EXCHANGER = "status_geothermal_heat_exchanger"
PARAM_RH_SENSOR_STATUS = "rh_sensor_status"
PARAM_CO1_SENSOR_STATUS = "co1_sensor_status"
PARAM_CO2_SENSOR_STATUS = "co2_sensor_status"
PARAM_CN1_POSITION = "cn1_position"
PARAM_CN2_POSITION = "cn2_position"
PARAM_CONTACT_1_EXHAUST_FAN_ACTION = "contact_1_exhaust_fan_action"
PARAM_CONTACT_2_EXHAUST_FAN_ACTION = "contact_2_exhaust_fan_action"
PARAM_CN1_SWITCH_INPUT_CONDITION = "cn1_switch_input_condition"
PARAM_CN2_SWITCH_INPUT_CONDITION = "cn2_switch_input_condition"

CN_SWITCH_INPUT_CONDITION_LABELS: dict[str, str] = {
    "0": "off",
    "1": "on",
    "2": "on_if_bypass_conditions_met",
    "3": "bypass_control",
    "4": "bedroom_valve",
}

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

RH_SENSOR_SENSITIVITY_LABELS: dict[str, str] = {
    "-2": "very_low",
    "-1": "low",
    "0": "normal",
    "1": "high",
    "2": "very_high",
}

BYPASS_VALVE_STATUS_LABELS: dict[int, str] = {
    0: "initialization",
    1: "opening",
    2: "closing",
    3: "open",
    4: "closed",
}

FILTER_FAULT_CONDITION_LABELS: dict[str, str] = {
    "0": "off",
    "1": "filter_condition_only",
    "2": "fault_condition_only",
    "3": "filter_and_fault_condition",
}

ACTIVE_CONTROL_STATUS_LABELS: dict[int, str] = {
    0: "Standby",
    1: "Bootloader",
    2: "Non-blocking Error",
    3: "Blocking Error",
    4: "Manual",
    5: "Holiday",
    6: "Night Ventilation",
    7: "Party",
    8: "Bypass Boost",
    9: "Normal Boost",
    10: "Auto CO2",
    11: "Auto eBus",
    12: "Auto Modbus",
    13: "Auto LAN/WLAN Portal",
    14: "Auto LAN/WLAN Local",
}

ACTIVE_CONTROL_STATUS_LABELS: dict[int, str] = {
    0: "standby",
    1: "bootloader",
    2: "non_locking_fault",
    3: "blocking_error",
    4: "manual",
    5: "holiday",
    6: "night_ventilation_mode",
    7: "party",
    8: "bypass_boost",
    9: "normal_boost",
    10: "auto_co2",
    11: "auto_ebus",
    12: "auto_modbus",
    13: "auto_lan_wlan_portal",
    14: "auto_lan_wlan_local",
}

BYPASS_OPERATION_LABELS: dict[str, str] = {
    "0": "Automatic",
    "1": "Bypass Closed",
    "2": "Bypass Open",
}

FAN_ACTION_LABELS: dict[str, str] = {
    "0": "fan_off",
    "1": "fan_absolute_minimum",
    "2": "fan_setting_1",
    "3": "fan_setting_2",
    "4": "fan_setting_3",
    "5": "fan_setting_0",
    "6": "fan_multiple_switch",
    "7": "fan_absolute_maximum",
    "8": "no_exhaust_fan_control",
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

FILTER_STATUS_LABELS: dict[int, str] = {
    0: "not_dirty",
    1: "dirty",
}

CONTACT_TYPE_LABELS: dict[str, str] = {
    "0": "normally_open",
    "1": "normally_closed",
}

ON_OFF_LABELS = {
    "0": "off",
    "1": "on",
}

OPERATING_MODE_LABELS: dict[str, str] = {
    "0": "automatic",
    "1": "manual",
    "2": "holiday",
    "3": "party",
    "4": "night_ventilation",
}

FAN_OPERATING_MODE_LABELS: dict[str, str] = {
    "0": "Automatic",
    "1": "Manual",
    "2": "Holiday",
    "3": "Party",
    "4": "Night ventilation",
}

VALVE_CONTROL_LABELS: dict[str, str] = {
    "0": "relay_output_1",
    "1": "relay_output_2",
    "2": "analog_output_1",
    "3": "analog_output_2",
}

_SIGNAL_OUTPUT_MODE_LABELS: dict[str, str] = {
    "0": "0V",
    "1": "24V",
}

SIGNAL_OUTPUT_MODE_LABELS: dict[str, str] = {
    "0": "Off",
    "1": "Only filtercondition",
    "2": "Only faultcondition",
    "3": "Filter and fault condition",
}

CN_CONDITIONS_LABELS: dict[str, str] = {
    "0": "Only filtercondition",
    "1": "Only faultcondition",
    "2": "Filter and fault condition",
}

FROST_PROTECTION_STATE_LABELS: dict[str, str] = {
    "0": "unknown",
    "1": "not_initialized",
    "2": "power_up_delay",
    "3": "no_frost",
    "4": "start_delay",
    "5": "wait_for_ice",
    "6": "heating",
    "7": "wait_for_fan_control",
    "8": "fan_control",
    "9": "fan_off",
    "10": "fan_restart",
    "11": "error",
    "12": "water_block_test",
}

FROST_PROTECTION_STATUS_LABELS: dict[int, str] = {
    0: "not_initialized",
    1: "power_up_delay",
    2: "no_frost",
    3: "no_frost_delay",
    4: "frost_control_start_delay",
    5: "wait_for_icing",
    6: "ice_detected_delay",
    7: "heating",
    8: "wait_for_free_heater",
    9: "fan_control_start_delay",
    10: "fan_control_wait",
    11: "fan_control",
    12: "fan_off_delay",
    13: "fan_off",
    14: "fan_restarting",
    15: "error",
    16: "periodic_coil_test",
}

FROST_PROTECTION_STATE_TRANSLATIONS: dict[str, str] = {
    "unknown": "Onbekend",
    "not_initialized": "Niet geïnitialiseerd",
    "power_up_delay": "Wachten op opstarten",
    "no_frost": "Geen vorst",
    "start_delay": "Opstartvertraging",
    "wait_for_ice": "Wachten op ijsvorming",
    "heating": "Verwarmen",
    "wait_for_fan_control": "Wachten op ventilatorregeling",
    "fan_control": "Ventilatorregeling",
    "fan_off": "Ventilator uit",
    "fan_restart": "Herstart ventilator",
    "error": "Fout",
    "water_block_test": "Waterbloktest",
}

PREHEATER_STATUS_LABELS: dict[int, str] = {
    0: "off",
    1: "auto",
    2: "lock_current",
    3: "lock_maximum",
}

GEOTHERMAL_HEAT_EXCHANGER_LABELS: dict[int, str] = {
    0: "open_low",
    1: "closed",
    3: "open_high",
}

CN_POSITION_LABELS: dict[str, str] = {
    "0": "closed",
    "1": "Open",
}

SUPPLY_FAN_ACTION_LABELS: dict[str, str] = {
    "0": "Supply fan off",
    "1": "Min. ventilation 50 m³/h",
    "2": "Air flow Level 1",
    "3": "Air flow Level 2",
    "4": "Air flow Level 3",
    "5": "Max. air flow",
    "6": "No control supply fan",
}

EXHAUST_FAN_ACTION_LABELS: dict[str, str] = {
    "0": "Extract fan off",
    "1": "Min. ventilation 50 m³/h",
    "2": "Air flow Level 1",
    "3": "Air flow Level 2",
    "4": "Air flow Level 3",
    "5": "Max. air flow",
    "6": "No control extract fan",
}

BINARY_SENSOR_LABELS: dict[str, str] = {
    "0": "off",
    "1": "on",
}

MODE_VALVE_24V_CONTROL_LABELS: dict[str, str] = {
    "0": "open",
    "1": "closed",
}

MODE_INPUT_LABELS: dict[str, str] = {
    "0": "Off",
    "1": "On",
}

PARAM_VENTILATION_MODE_0 = "ventilation_mode_0_airflow"
PARAM_VENTILATION_MODE_1 = "ventilation_mode_1_airflow"
PARAM_VENTILATION_MODE_2 = "ventilation_mode_2_airflow"
PARAM_VENTILATION_MODE_3 = "ventilation_mode_3_airflow"

PARAM_SWITCH_TEMP_1 = "switch_temp_1"
PARAM_SWITCH_TEMP_2 = "switch_temp_2"

PARAM_IMBALANCE_FIREPLACE = "imbalance_fireplace"
PARAM_BYPASS_TEMPERATURE = "bypass_temperature"
PARAM_BYPASS_HYSTERESIS = "bypass_hysteresis"
PARAM_MINIMUM_INTAKE_TEMPERATURE = "minimum_intake_temperature"
PARAM_BYPASS_FUNCTION = "bypass_function"
PARAM_MODE_VALVE_24V_CONTROL = "mode_valve_24v_control"
PARAM_VALVE_CONTROL = "valve_control"
PARAM_SIGNAL_OUTPUT_MODE = "signal_output_mode"
PARAM_FILTER_STATUS = "filter_status"
PARAM_FILTER_MESSAGE = "filter_message"
PARAM_CN1_SWITCH_INPUT = "cn1_switch_input"
PARAM_CN2_SWITCH_INPUT = "cn2_switch_input"
PARAM_EXHAUST_AIR_PRESSURE = "exhaust_air_pressure"
PARAM_SUPPLY_AIR_PRESSURE = "supply_air_pressure"
PARAM_RH_SENSOR_SENSITIVITY = "rh_sensor_sensitivity"
PARAM_DAYS_UNTIL_FILTER_MESSAGE = "days_until_filter_message"
PARAM_CO2_SENSOR_1_MIN_PPM = "co2_sensor_1_min_ppm"
PARAM_CO2_SENSOR_1_MAX_PPM = "co2_sensor_1_max_ppm"
PARAM_CO2_SENSOR_2_MIN_PPM = "co2_sensor_2_min_ppm"
PARAM_CO2_SENSOR_2_MAX_PPM = "co2_sensor_2_max_ppm"
PARAM_CO2_SENSOR_3_MIN_PPM = "co2_sensor_3_min_ppm"
PARAM_CO2_SENSOR_3_MAX_PPM = "co2_sensor_3_max_ppm"
PARAM_CO2_SENSOR_4_MIN_PPM = "co2_sensor_4_min_ppm"
PARAM_CO2_SENSOR_4_MAX_PPM = "co2_sensor_4_max_ppm"

PARAMETER_NAMES = {
    16000: "device_type",
    16001: "nominal_supply_air_flow",
    16002: "nominal_exhaust_air_flow",
    16006: "filter_status",
    16007: "days_since_filter_reset",
    16009: "active_control_status",
    16011: "ventilation_level",
    16012: "operating_mode",
    16015: "actual_supply_air_flow",  # Sensor
    16016: "supply_air_flow_setpoint",
    16017: "exhaust_air_flow",
    16018: "exhaust_air_flow_setpoint",
    16019: "fresh_air_temp",
    16020: "supply_air_temp",  # Sensor
    16021: "exhaust_air_temp",
    16022: "discharge_air_temp",
    16024: "bypass_valve_status",
    16025: "preheater_status",
    16031: "ventilation_mode_0_airflow",
    16032: "ventilation_mode_1_airflow",
    16033: "ventilation_mode_2_airflow",
    16034: "ventilation_mode_3_airflow",
    16038: "supply_air_pressure",
    16039: "exhaust_air_pressure",
    16041: "bypass_valve_status",  # Enum sensor (duplicaat van 16024)
    16042: "bypass_temperature",
    16043: "bypass_hysteresis",
    16044: "bypass_operation",
    16048: "frost_protection_status",  # Enum sensor
    16049: "preheater_power",
    16054: "filter_message",
    16055: "days_since_filter_reset",
    16057: "days_until_filter_message",
    16059: "relative_humidity",
    16060: "rh_sensor_status",  # Binary sensor
    16061: "rh_sensor_sensitivity",
    16062: "ebus_co2_sensor_status",  # Binary sensor
    16064: "co2_sensor_1",
    16065: "co2_sensor_1_min_ppm",
    16066: "co2_sensor_1_max_ppm",
    16068: "co2_sensor_2",
    16069: "co2_sensor_2_min_ppm",
    16070: "co2_sensor_2_max_ppm",
    16072: "co2_sensor_3",
    16073: "co2_sensor_3_min_ppm",
    16074: "co2_sensor_3_max_ppm",
    16076: "co2_sensor_4",
    16077: "co2_sensor_4_min_ppm",
    16078: "co2_sensor_4_max_ppm",
    16088: "status_geothermal_heat_exchanger",  # Enum sensor
    16089: "additional_temperature_sensor",
    16090: "cn1_switch_input",  # Binary sensor
    16091: "cn2_switch_input",  # Binary sensor
    16095: "v1_analog_input",  # Voltage sensor
    16096: "v2_analog_input",  # Voltage sensor
    16099: "v1_minimum_voltage",
    16100: "v1_maximum_voltage",
    16101: "cn1_switch_input_condition",
    16102: "v2_minimum_voltage",
    16103: "v2_maximum_voltage",
    16104: "cn2_switch_input_condition",
    16106: "signal_output_mode",
    16116: "imbalance_fireplace",
    16118: "minimum_intake_temperature",
    16125: "mode_input_1",
    16126: "contact_1_type",
    16127: "contact_1_supply_fan_action",
    16128: "contact_1_exhaust_fan_action",
    16129: "contact_2_type",
    16130: "contact_2_supply_fan_action",
    16131: "contact_2_exhaust_fan_action",
    16132: "mode_input_2",
    16134: "switch_temp_1",
    16135: "switch_temp_2",
    16136: "mode_valve_24v_control",
    16137: "valve_control",
    16143: "bypass_operation",
    21002: "deviceTypeTitle",
    21008: "ip_address",
    21009: "subnet_mask",
    21010: "default_gateway",
    21011: "dns_server",
    21012: "dhcp_active",
    21013: "wifi_active",
    21014: "internet_connection_enabled",
    21015: "lan_mac_address",
    21016: "wifi_mac_address",
    21017: "system_name",
}

UID_PARAMETER_MAP: dict[int, str] = {
    # Airflows
    8: "supply_air_flow",
    9: "exhaust_air_flow",
    10: "supply_air_flow_setpoint",
    11: "exhaust_air_flow_setpoint",

    # Ventilation
    17: "ventilation_level",
    18: "ventilation_level_requested",

    # Pressures
    19: "supply_duct_pressure",
    20: "exhaust_duct_pressure",

    # Statuses
    21: "bypass_status",
    22: "frost_protection_status",
    23: "preheater_status",
    30: "filter_status",
    32: "operating_mode",
    35: "active_control_status",
    44: "bypass_operation",

    # Temperatures (tentative)
    45: "outdoor_air_temperature",
    51: "supply_air_temperature",
    53: "extract_air_temperature",

    # Humidity
    52: "supply_air_humidity",
    54: "extract_air_humidity",

    # Software versions
    70: "software_version_base",
    73: "software_version_uif",
    78: "software_version_webserver",

    # Network
    91: "ip_address",

    60000: "default_gateway",
    60001: "subnet_mask",
    60002: "primary_dns",
    60003: "secondary_dns",

    # Brink Home
    60004: "home_module_name",
    60005: "destination_server",
    60006: "destination_server_port",

    # Wireless / network (unknown)
    60011: "wifi_ssid_1",
    60012: "wifi_password_1",
    60013: "wifi_ssid_2",
    60014: "wifi_password_2",
    60015: "wifi_ssid_3",
    60016: "wifi_password_3",
    60017: "wifi_ssid_4",
    60018: "wifi_password_4",

    # Router / provider (tentative)
    60019: "router_name",
    60020: "provider_name",
}

ACTUALS_UID_MAP: dict[int, str] = {
    10000: "ventilation_level",

    10060: "supply_air_flow",
    10120: "exhaust_air_flow",

    10180: "supply_duct_pressure",
    10240: "exhaust_duct_pressure",

    10300: "bypass_status",
    10360: "frost_protection_status",
    10420: "preheater_status",

    10480: "supply_air_temperature",
    10540: "extract_air_temperature",
    10600: "outdoor_air_temperature",

    10660: "supply_air_humidity",
    10720: "extract_air_humidity",

    10780: "supply_fan_rpm",
    10840: "exhaust_fan_rpm",

    10900: "co2_sensor_1",
    10960: "co2_sensor_2",
    11020: "co2_sensor_3",
    11080: "co2_sensor_4",

    11100: "humidity_sensor",

    11140: "software_version_base",
    11200: "software_version_uif",
    11260: "software_version_webserver",
    11320: "software_version_webapp",
    11380: "software_version_extension",

    11440: "device_serial_number",

    11500: "days_until_filter_message",

    13180: "dipswitch_value",

    13240: "ip_address",
    13300: "default_gateway",
    13360: "subnet_mask",
    13420: "primary_dns",
    13480: "secondary_dns",

    13540: "home_module_name",

    13600: "destination_server",
    13660: "destination_server_port",
}

ERROR_CATEGORY_LABELS: dict[int, str] = {
    20000: "self_test_failed",
    20060: "flash_error",
    20120: "eeprom_error",
    20960: "bypass_fault",
    21800: "uif_fault",
    22160: "ebus_fault",
    22700: "usb_fault",
}

ERROR_COMPONENT_LABELS: dict[int, str] = {
    20180: "requested_supply_airflow",
    20240: "requested_exhaust_airflow",
    20300: "outdoor_air_temperature",
    20360: "supply_fan",
    20420: "supply_fan_rpm",
    20480: "supply_fan_anemometer",
    20540: "supply_fan_temperature_sensor",
    20600: "supply_fan_humidity_sensor",
    20720: "exhaust_fan",
    20780: "exhaust_fan_rpm",
    20840: "exhaust_fan_anemometer",
    21200: "outdoor_temperature_sensor",
    21320: "external_humidity_sensor",
    21440: "four_position_switch",
    21500: "24v_four_position_switch",
    21560: "internal_preheater",
    21620: "external_preheater",
    21680: "external_reheater",
    21740: "relay_output",
    22100: "ebus_co2_sensor",
}

ERROR_STATE_LABELS: dict[int, str] = {
    23000: "not_reached",
    23060: "too_high",
    23120: "fault",
    23180: "not_running",
    23240: "too_low",
    23300: "too_high",
    23360: "no_communication",
    23420: "communication_error",
    23480: "fault",
    23540: "temperature_sensor_fault",
    23600: "humidity_sensor_fault",
    23660: "detected",
    23720: "not_connected",
    23780: "value_too_low",
    24140: "too_warm",
    24200: "short_circuit",
    24320: "overvoltage",
    24380: "wrong_master",
    24440: "no_communication",
    24500: "sensor_fault",
    24620: "unknown_position",
    24680: "short_circuit",
}

PARAMETER_UID_MAP: dict[int, str] = {
    0: "ventilation_mode_0_airflow",      # 150
    1: "ventilation_mode_1_airflow",      # 225
    2: "ventilation_mode_2_airflow",      # 300
    3: "ventilation_mode_3_airflow",      # 240

    4: "imbalance_fireplace",             # 100
    5: "default_ventilation_level",       # 0

    10: "days_until_filter_message",      # 210

    24: "minimum_co2_sensor_1",           # 50
    25: "maximum_co2_sensor_1",           # 250

    44: "humidity_sensor_sensitivity",    # 25

    45: "contact_1_type",                 # 1
    46: "cn1_conditions",                 # 2

    47: "contact_1_supply_fan_action",    # 400
    48: "contact_1_supply_fan_action_max",

    49: "contact_1_exhaust_fan_action",   # 400
    50: "contact_1_exhaust_fan_action_max",

    51: "contact_2_supply_fan_action",    # 400
    52: "contact_2_supply_fan_action_max",

    53: "contact_2_exhaust_fan_action",   # 400
    54: "contact_2_exhaust_fan_action_max",

    55: "mode_input_1",
    56: "v1_minimum_voltage",
    57: "v1_maximum_voltage",

    58: "mode_input_2",
    59: "v2_minimum_voltage",
    60: "v2_maximum_voltage",

    61: "status_geothermal_heat_exchanger",

    62: "switch_temperature_1",
    63: "switch_temperature_2",

    67: "mode_valve_24v_control",

    69: "valve_control",

    70: "signal_output_mode",
}

PARAMETER_UID_TO_KEY: dict[int, str] = {
    # Ventilation
    1: "ventilation_mode_1_airflow",
    2: "ventilation_mode_2_airflow",
    3: "ventilation_mode_3_airflow",
    29: "ventilation_mode_0_airflow",

    # Bypass
    4: "bypass_open_temperature",
    5: "bypass_close_temperature",
    26: "bypass_operation",
    44: "bypass_hysteresis",
    66: "bypass_function",
    67: "bypass_boost_level",

    # Fireplace / imbalance
    64: "imbalance_supply",
    65: "imbalance_exhaust",
    93: "imbalance_fireplace",

    # Default ventilation level
    58: "default_ventilation_level",

    # Frost / preheater
    68: "frost_protection_temperature_offset",
    103: "minimum_intake_temperature",

    # Filter
    69: "days_until_filter_message",

    # CO2
    47: "co2_sensor_1_min_ppm",
    48: "co2_sensor_1_max_ppm",
    49: "co2_sensor_2_min_ppm",
    50: "co2_sensor_2_max_ppm",
    51: "co2_sensor_3_min_ppm",
    52: "co2_sensor_3_max_ppm",
    53: "co2_sensor_4_min_ppm",
    54: "co2_sensor_4_max_ppm",
    55: "ebus_co2_sensor_status",

    # Humidity
    45: "humidity_sensor_enabled",
    46: "rh_sensor_sensitivity",

    # Contact 1
    11: "contact_1_type",
    14: "cn1_conditions",
    15: "contact_1_supply_fan_action",
    16: "contact_1_exhaust_fan_action",

    # Contact 2
    17: "contact_2_type",
    20: "cn2_conditions",
    21: "contact_2_supply_fan_action",
    22: "contact_2_exhaust_fan_action",

    # 0-10V input 1
    79: "mode_input_1",
    12: "v1_minimum_voltage",
    13: "v1_maximum_voltage",

    # 0-10V input 2
    80: "mode_input_2",
    18: "v2_minimum_voltage",
    19: "v2_maximum_voltage",

    # Geothermal heat exchanger
    23: "geothermal_heat_exchanger_enabled",
    24: "switch_temperature_1",
    25: "switch_temperature_2",

    # Valve control
    82: "mode_valve_24v_control",
    81: "valve_control",

    # Signal output
    102: "signal_output_mode",

    # Network
    107: "network_method",
    108: "network_configuration",
    110: "advanced_network_configuration",
    111: "reset_network",

    # Bus communication
    84: "bus_connection_type",
    59: "slave_address",
    60: "baudrate",
    61: "parity",

    # Localization
    88: "language",
    89: "date_time_format",
    104: "daylight_saving_time",

    # Miscellaneous
    6: "device_configuration",
    7: "standby_mode",
    8: "fireplace_enabled",
    9: "external_humidity_sensor_enabled",
    10: "external_humidity_sensor_temperature",
    30: "preheater_enabled",
    83: "standby_command",
}

LOCAL_UID_TO_KEY = {
    1: "ventilation_level",
    17: "bypass_status",
    18: "frost_protection_status",
    19: "supply_air_flow",
    20: "exhaust_air_flow",
    21: "heater_status",
    52: "supply_humidity",
    54: "exhaust_humidity",
    83: "time",
    84: "date",
    91: "ip_address",
}

LOCAL_UID_TO_PARAMETER_ID: dict[int, int] = {
    0: 16001,   # ventilation_level
    1: 16001,   # ventilation_mode
    11: 16057,  # Dagen tot filtermelding
    17: 16023,  # bypass_status
    18: 16024,  # frost_protection_status
    19: 16015,  # Actuele toevoerdebiet m³/h
    20: 16017,  # Actuele afvoerdebiet m³/h
    21: 16025,  # preheater_status
    51: 16019,  # Temperatuur toevoer (?)
    52: 16059,  # Relatieve vochtigheid toevoer
    53: 16020,  # Temperatuur buiten
    54: 16028,  # exhaust_humidity
    #    83: # Tijd
    #    84: # Datum
    #    91: # IP-adres
}

READ_WRITE_MAP = {
    0: "hidden",
    1: "read-only",
    3: "read-write",
}

MODE_MANUAL_VALUE = "1"
WRITE_VALUE_STATE = 0


@dataclass(frozen=True, slots=True)
class BrinkError:
    """Describe a Brink error."""

    code: str
    blocking: bool
    title: str
    description: str


ERRORS: dict[str, BrinkError] = {
    "E1124": BrinkError(
        code="E1124",
        blocking=True,
        title="Exhaust fan",
        description="No communication",
    ),
    "E1125": BrinkError(
        code="E1125",
        blocking=True,
        title="Supply fan",
        description="No communication",
    ),
}
