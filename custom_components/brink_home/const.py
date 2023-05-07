"""Constant values for the Brink Home component."""

DOMAIN = "brink_home"
DEFAULT_NAME = "Brink"
DEFAULT_MODEL = "Zone"

DATA_CLIENT = "brink_client"
DATA_COORDINATOR = "coordinator"
DATA_DEVICES = "systems"

DEFAULT_SCAN_INTERVAL = 30

API_URL = "https://www.brink-home.com/portal/api/portal/"

NAMES = {
    "Lüftungsstufe": "Ventilation power",
    "Betriebsart": "Ventilation mode",
    "Restlaufzeit Betriebsartfunktion": "Remaining run time operating mode function",
    "Status Filtermeldung": "Filter message status"
}

MODES = {
    "0": "Automatic",
    "1": "Manual",
    "2": "Holiday",
    "3": "Party",
    "4": "Night",
}

MODE_TO_VALUE = {
    "Automatic": "0",
    "Manual": "1",
    "Holiday": "2",
    "Party": "3",
    "Night": "4"
}

