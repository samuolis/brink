from __future__ import annotations

# api.py
import asyncio
import logging

from aiohttp import ClientError as ClientError
from aiohttp import ClientResponseError as ClientResponseError

from .const import (
    DEFAULT_MODEL,
    DEFAULT_NAME,
    PARAM_DEVICE_TYPE,
    PARAM_SOFTWARE_LABEL,
)
from .core.brink_home_cloud import BrinkHomeCloud
from .models import BrinkAlertLevel, BrinkDeviceData

_LOGGER = logging.getLogger(__name__)
PARAM_IP_ADDRESS = "ip_address"
PARAM_DNS_SERVER = "dns_server"
PARAM_API_ONLINE = "api_is_online"


async def async_get_devices(brink_client: BrinkHomeCloud) -> dict[int, BrinkDeviceData]:
    """Fetch and normalize Brink systems plus the parameters this integration uses."""
    systems = await brink_client.get_systems()

    _LOGGER.debug("Brink Flair nr of systems: %s", len(systems))

    # device = await brink_client.get_device(3074)

    # _LOGGER.debug("Brink Flair device: %s", device)

    # gateway_type_id = device.get("gatewayTypeId")
    # is_online = device.get("isOnline")

    # _LOGGER.debug("Brink Flair gateway_type_id: %s", gateway_type_id) # always 3 ?
    # _LOGGER.debug("Brink Flair device is_online: %s", is_online)

    devices: dict[int, BrinkDeviceData] = {}

    for system in systems:
        system_id = int(system["system_id"])
        is_system_owner = system["is_system_owner"]
        is_editable = system["is_editable"]
        access_level = system["access_level"]
        owner_group_name = system["owner_group_name"]
        is_favorite = system["is_favorite"]
        gateway_state = system["gateway_state"]
        reported_alert_count = system.get("active_alert_count")
        iana_time_zone = system["iana_time_zone"]
        two_letter_country_code = system["two_letter_country_code"]
        user_group_names = system["user_group_names"]
        total_count = system["total_count"]
        device, alerts, parameters = await asyncio.gather(
            brink_client.async_get_device(system_id),
            brink_client.async_get_active_alerts(system_id),
            brink_client.get_device_data(system_id),
        )
        active_alert_count = (
            reported_alert_count
            if isinstance(reported_alert_count, int)
            and not isinstance(reported_alert_count, bool)
            and reported_alert_count >= 0
            else len(alerts)
        )
        _LOGGER.debug("Fetched %s active alerts", len(alerts))
        gateway_type_id = device.get("gatewayTypeId")
        is_online = device.get("isOnline")
        has_blocking = any(
            alert.level == BrinkAlertLevel.BLOCKING for alert in alerts
        )
        devices[system_id] = BrinkDeviceData(
            api_is_online=True,
            system_id=system_id,
            name=system.get("name") or DEFAULT_NAME,
            internal_name=system.get("name")
            or system.get("name")
            or DEFAULT_NAME,
            serial_number=system.get("serial_number"),
            gateway_state=system.get("gateway_state"),
            gateway_type_id=gateway_type_id,
            device_is_online=bool(is_online),
            ip_address=(
                str(parameters[PARAM_IP_ADDRESS]["value"])
                if PARAM_IP_ADDRESS in parameters
                else None
            ),
            dns_server=(
                str(parameters[PARAM_DNS_SERVER]["value"])
                if PARAM_DNS_SERVER in parameters
                else None
            ),
            model=str(
                parameters.get(PARAM_DEVICE_TYPE, {}).get("value")
                or DEFAULT_MODEL
            ),
            sw_version=(
                str(parameters.get(PARAM_SOFTWARE_LABEL, {}).get("value"))
                if parameters.get(PARAM_SOFTWARE_LABEL, {}).get("value") is not None
                else None
            ),
            parameters=parameters,
            alerts=alerts,
            has_blocking_error=has_blocking,
            is_system_owner=is_system_owner,
            is_editable=is_editable,
            access_level=access_level,
            owner_group_name=owner_group_name,
            is_favorite=is_favorite,
            active_alert_count=active_alert_count,
            iana_time_zone=iana_time_zone,
            two_letter_country_code=two_letter_country_code,
            user_group_names=user_group_names,
            total_count=total_count,
        )

    return devices
