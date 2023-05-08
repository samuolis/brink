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
        menu_items = result.get("menuItems", [])
        menu_item = menu_items[0]
        pages = menu_item.get("pages", [])
        home_page = pages[0]
        parameters = home_page.get("parameterDescriptors", [])
        ventilation = parameters[0]
        mode = parameters[1]
        mode_remaining_time = parameters[2]
        filters_need_change = parameters[3]

        description_result = {
            "ventilation": self.__get_type(ventilation),
            "mode": self.__get_type(mode),
            "mode_remaining_time": self.__get_type(mode_remaining_time),
            "filters_need_change": self.__get_type(filters_need_change)
        }

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
                    'Value': value,
                }
            ],
            'SendInOneBundle': True,
            'DependendReadValuesAfterWrite': [
                ventilation["value_id"],
                mode["value_id"]
            ]
        }

        url = f"{API_URL}WriteParameterValuesAsync"

        response = await self._api_call(url, "POST", data)
        result = await response.json()

        mapped_result = self.__map_write_result(result, ventilation, mode)

        _LOGGER.debug(
            "set_ventilation_value result: %s",
            mapped_result
        )

        return mapped_result

    async def set_mode_value(self, system_id, gateway_id, mode, ventilation, value):
        mode_value = mode["values"][value]["value"]
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
            'DependendReadValuesAfterWrite': [
                mode["value_id"],
                ventilation["value_id"]
            ]
        }

        url = f"{API_URL}WriteParameterValuesAsync"

        response = await self._api_call(url, "POST", data)
        result = await response.json()

        mapped_result = self.__map_write_result(result, ventilation, mode)

        _LOGGER.debug(
            "set_mode_value result: %s",
            mapped_result
        )

        return mapped_result

    def __map_write_result(self, result, ventilation, mode):
        new_ventilation_value = None
        new_mode_value = None
        for value in result:
            if value["valueId"] == ventilation["value_id"]:
                new_ventilation_value = value["value"]
            if value["valueId"] == mode["value_id"]:
                new_mode_value = value["value"]

        return {
            "mode_value": new_mode_value,
            "ventilation_value": new_ventilation_value
        }
