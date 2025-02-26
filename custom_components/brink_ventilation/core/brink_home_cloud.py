"""Implementation for Brink-Home Cloud"""
import asyncio
import async_timeout
import logging
import aiohttp

from ..const import API_URL
from ..translations import TRANSLATIONS

_LOGGER = logging.getLogger(__name__)


class BrinkHomeCloud:
    """Interacts with Brink Home via public API."""

    def __init__(self, session: aiohttp.ClientSession, username: str, password: str):
        """Performs login and save session cookie."""
        self.timeout = 20
        self.headers = {
            "X-Requested-With": "XMLHttpRequest",
            "User-Agent": "okhttp/3.11.0",
            "Content-Type": "application/json; charset=UTF-8",
        }

        self._http_session = session
        self._username = username
        self._password = password

    async def _api_call(self, url, method, data=None):
        _LOGGER.debug(
            "%s request: %s, data %s",
            method,
            url,
            data
        )
        try:
            async with async_timeout.timeout(self.timeout):
                req = await self._http_session.request(
                    method,
                    url,
                    json=data,
                    headers=self.headers
                )

            if req.status == 401:
                _LOGGER.error("Client unauthorized on API %s request", url)
                await self.login()
                req = await self._api_call(url, method, data)

            req.raise_for_status()
            return req

        except aiohttp.ClientError as err:
            _LOGGER.error("Client error on API %s request %s", url, err)
            raise

        except asyncio.TimeoutError:
            _LOGGER.error("Client timeout error on API request %s", url)
            raise

    async def login(self):
        data = {
            'UserName': self._username,
            'Password': self._password,
        }

        url = f"{API_URL}UserLogon"

        resp = await self._api_call(url, "POST", data)
        result = await resp.json()
        self.token_exists = True

        _LOGGER.debug(
            "login result: %s",
            result
        )

        return result

    async def get_systems(self):
        """Gets systems list."""
        url = f"{API_URL}GetSystemList"

        response = await self._api_call(url, "GET")
        result = await response.json()

        mapped_result = []

        for system in result:
            mapped_result.append({
                'system_id': system["id"],
                'gateway_id': system["gatewayId"],
                'name': system['name']
        })

        _LOGGER.debug(
            "get_systems result: %s",
            mapped_result
        )

        return mapped_result

    async def get_description_values(self, system_id, gateway_id):
        """Gets values info."""
        url = f"{API_URL}GetAppGuiDescriptionForGateway?GatewayId={gateway_id}&SystemId={system_id}"

        response = await self._api_call(url, "GET")
        result = await response.json()

        _LOGGER.debug(
            "Response result: %s",
            result
        )
        
        menu_items = result.get("menuItems", [])
        if not menu_items:
            _LOGGER.debug("No menu items found in API response")
            return {}
            
        menu_item = menu_items[0]
        pages = menu_item.get("pages", [])
        if not pages:
            _LOGGER.debug("No pages found in menu item")
            return {}
            
        # Extract all parameters from all pages
        all_parameters = []
        for page in pages:
            parameters = page.get("parameterDescriptors", [])
            all_parameters.extend(parameters)
            
        _LOGGER.debug(f"Found {len(all_parameters)} parameters across all pages")

        # Find the basic parameters
        ventilation = self.__find(all_parameters, "uiId", "Lüftungsstufe")
        mode = self.__find(all_parameters, "uiId", "Betriebsart")
        filters_need_change = self.__find(all_parameters, "uiId", "Status Filtermeldung")
        
        # Initialize the result dictionary with the basic parameters
        description_result = {
            "ventilation": self.__get_type(ventilation),
            "mode": self.__get_type(mode),
            "filters_need_change": self.__get_type(filters_need_change)
        }
        
        # Look for CO2 sensors and other sensors and add them to the result
        for param in all_parameters:
            param_name = param.get("name", "")
            
            # Add CO2 sensors
            if "PPM eBus CO2-sensor" in param_name or "PPM CO2-sensor" in param_name:
                _LOGGER.debug(f"Found CO2 sensor: {param_name}")
                description_result[param_name] = self.__get_type(param)
                
            # Add temperature sensors
            elif "temperatur" in param_name.lower():
                _LOGGER.debug(f"Found temperature sensor: {param_name}")
                description_result[param_name] = self.__get_type(param)
                
            # Add humidity sensors
            elif "feuchte" in param_name.lower():
                _LOGGER.debug(f"Found humidity sensor: {param_name}")
                description_result[param_name] = self.__get_type(param)

        _LOGGER.debug(
            "get_description_values result: %s",
            description_result
        )

        return description_result

    def __get_type(self, type):
        return {
            "name": TRANSLATIONS.get(type["name"], type["name"]),
            "value_id": type["valueId"],
            "value": type["value"],
            "values": self.__get_values(type)
        }

    @staticmethod
    def __get_values(type):
        values = type["listItems"]
        extracted = []
        for value in values:
            if value["isSelectable"]:
                extracted.append({
                    "value": value["value"],
                    "text": TRANSLATIONS.get(value["displayText"], value["displayText"])
                })

        return extracted

    # 1 as mode value changes mode to manual every time you change ventilation value
    async def set_ventilation_value(self, system_id, gateway_id, mode, ventilation, value):
        ventilation_value = ventilation["values"][value]["value"]
        if ventilation_value is None:
            return
        data = {
            'GatewayId': gateway_id,
            'SystemId': system_id,
            'WriteParameterValues': [
                {
                    'ValueId': mode["value_id"],
                    'Value': '1',
                },
                {
                    'ValueId': ventilation["value_id"],
                    'Value': ventilation_value,
                }
            ],
            'SendInOneBundle': True,
            'DependendReadValuesAfterWrite': []
        }

        url = f"{API_URL}WriteParameterValuesAsync"

        await self._api_call(url, "POST", data)

    async def set_mode_value(self, system_id, gateway_id, mode, value):
        mode_value = self.__find(mode["values"], "text", value)["value"]
        if mode_value is None:
            return
        data = {
            'GatewayId': gateway_id,
            'SystemId': system_id,
            'WriteParameterValues': [
                {
                    'ValueId': mode["value_id"],
                    'Value': mode_value,
                },
            ],
            'SendInOneBundle': True,
            'DependendReadValuesAfterWrite': []
        }

        url = f"{API_URL}WriteParameterValuesAsync"

        await self._api_call(url, "POST", data)

    def __find(self, arr , attr, value):
        for obj in arr:
            try:
                if obj[attr] == value:
                    return obj
            except:
                _LOGGER.debug(
                    "find error: %s",
                    value
                )

