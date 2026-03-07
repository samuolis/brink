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

PARAM_NAME_MAP: dict[str, str] = {
    "deviceTypeTitle": PARAM_DEVICE_TYPE,
    "softwareLabel": PARAM_SOFTWARE_LABEL,
    "Lüftungsstufe": PARAM_VENTILATION_LEVEL,
    "Betriebsart": PARAM_OPERATING_MODE,
    "Status Filtermeldung": PARAM_FILTER_STATUS,
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
