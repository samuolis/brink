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
}

MODES = {
    "Automatikbetrieb": "Automatic",
    "Handbetrieb": "Manual",
    "Urlaubbetrieb": "Holiday",
    "Partybetrieb": "Party",
    "Nachtlüftungsbetrieb": "Night",
}

MODE_TO_VALUE = {
    "Automatic": "0",
    "Manual": "1",
    "Holiday": "2",
    "Party": "3",
    "Night": "4"
}

