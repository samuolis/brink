"""Constant values for the Eldes component."""

DOMAIN = "brink_home"
DEFAULT_NAME = "Eldes"
DEFAULT_ZONE = "Zone"

DATA_CLIENT = "eldes_client"
DATA_COORDINATOR = "coordinator"
DATA_DEVICES = "devices"

DEFAULT_SCAN_INTERVAL = 30

API_URL = "https://www.brink-home.com/portal/api/portal/"

API_PATHS = {
    "AUTH": "UserLogon/",
    "DEVICE": "device/",
}

ALARM_MODES = {
    "DISARM": "disarm",
    "ARM_AWAY": "arm",
    "ARM_HOME": "armstay",
}

OUTPUT_TYPES = {
    "SWITCH": "SWITCH",
}

OUTPUT_ICONS_MAP = {
    "ICON_0": "mdi:fan",
    "ICON_1": "mdi:lightning-bolt-outline",
    "ICON_2": "mdi:power-socket-eu",
    "ICON_3": "mdi:power-plug",
}

SIGNAL_STRENGTH_MAP = {
    0: 0,
    1: 30,
    2: 60,
    3: 80,
    4: 100,
}

BATTERY_STATUS_MAP = {
    True: "OK",
    False: "Bad",
}

ATTR_EVENTS = "events"
ATTR_ALARMS = "alarms"
ATTR_USER_ACTIONS = "user_actions"
