"""Verify alert diagnostics without Brink's optional summary counter."""

from __future__ import annotations

import logging
from asyncio import CancelledError
from collections.abc import Iterable
from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, call

import pytest
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import EntityPlatform
from tests.ha_test_support import MockConfigEntry

from custom_components.brink_ventilation.api import async_get_devices
from custom_components.brink_ventilation.const import DOMAIN
from custom_components.brink_ventilation.coordinator import BrinkCoordinator
from custom_components.brink_ventilation.core.brink_home_cloud import (
    BrinkApiError,
    BrinkHomeCloud,
)
from custom_components.brink_ventilation.models import BrinkDeviceData
from custom_components.brink_ventilation.sensor import (
    SENSOR_DESCRIPTIONS,
    BrinkHomeSensorEntity,
)

_OMITTED = object()


def _alert_payload(alert_id: int, *, is_active: bool = True) -> dict[str, object]:
    """Build a synthetic portal alert with a timezone-aware timestamp."""
    return {
        "id": alert_id,
        "componentId": 1,
        "code": 100,
        "level": 1,
        "isActive": is_active,
        "isArchived": False,
        "incoming": "2026-10-28T00:00:00+00:00",
        "outgoing": None,
    }


def _cloud_client(pages: Iterable[dict[str, object]]) -> BrinkHomeCloud:
    """Create a real client with its alert HTTP boundary replaced."""
    client = BrinkHomeCloud(MagicMock(), "test-user", "test-password")
    client.async_get_alerts = AsyncMock(side_effect=list(pages))
    return client


async def _fetch_devices(
    client: BrinkHomeCloud,
    summary: object,
    *,
    device_is_online: bool = True,
    system_ids: tuple[int, ...] = (101,),
) -> dict[int, BrinkDeviceData]:
    """Normalize synthetic systems through the real client and API adapter."""
    systems: list[dict[str, object]] = []
    for identifier in system_ids:
        system: dict[str, object] = {
            "systemShareId": identifier,
            "systemName": "Synthetic unit",
        }
        if summary is not _OMITTED:
            system["activeAlertCount"] = summary
        systems.append(system)
    response = MagicMock()
    response.json = AsyncMock(return_value={"items": systems})
    response.release = AsyncMock()
    client._api_request = AsyncMock(return_value=response)
    client.async_get_device = AsyncMock(
        return_value={"gatewayTypeId": 3, "isOnline": device_is_online}
    )
    client.get_device_data = AsyncMock(return_value={})
    return await async_get_devices(client)


def _count_sensor(
    client: BrinkHomeCloud, coordinator: BrinkCoordinator | MagicMock
) -> BrinkHomeSensorEntity:
    """Create the shipped active-alert diagnostic without replacing its behavior."""
    description = next(
        item for item in SENSOR_DESCRIPTIONS if item.key == "active_alert_count"
    )
    return BrinkHomeSensorEntity(client, coordinator, 101, description)


@pytest.mark.parametrize(
    "summary",
    [
        pytest.param(_OMITTED, id="omitted"),
        None,
        -1,
        True,
        False,
        "invalid",
        "2",
        1.5,
        {"alertCount": -1},
        {"alertCount": True},
        {"alertCount": "2"},
        {"alertCount": 1.5},
        {"unexpected": 2},
        {},
    ],
)
@pytest.mark.parametrize("alert_count", [0, 2])
@pytest.mark.parametrize("device_is_online", [False, True])
async def test_count_uses_fetched_alerts_when_summary_is_unusable(
    summary: object, alert_count: int, device_is_online: bool
) -> None:
    """Keep valid zero/nonzero diagnostics available without a portal summary."""
    client = _cloud_client(
        [{"items": [_alert_payload(index) for index in range(alert_count)]}]
    )
    devices = await _fetch_devices(client, summary, device_is_online=device_is_online)
    coordinator = MagicMock(last_update_success=True, data=devices)
    entity = _count_sensor(client, coordinator)

    assert devices[101].active_alert_count == alert_count
    assert type(devices[101].active_alert_count) is int
    assert entity.available is True
    assert entity.native_value == alert_count
    assert entity.unique_id == "brink_ventilation_101_active_alert_count_sensor"

    coordinator.last_update_success = False
    assert entity.available is False


async def test_count_uses_all_alert_pages() -> None:
    """Count per-system alerts beyond the portal's first ten records."""
    client = _cloud_client(
        [
            {
                "items": [_alert_payload(index) for index in range(10)],
                "totalCount": 12,
            },
            {"items": [_alert_payload(10), _alert_payload(11)], "totalCount": 12},
        ]
    )
    devices = await _fetch_devices(client, None)
    coordinator = MagicMock(last_update_success=True, data=devices)
    entity = _count_sensor(client, coordinator)

    assert devices[101].active_alert_count == 12
    assert entity.available is True
    assert entity.native_value == 12
    assert client.async_get_alerts.await_args_list == [
        call(101, page_index=0),
        call(101, page_index=1),
    ]


@pytest.mark.parametrize("payload", [{}, {"items": None}, {"items": "invalid"}])
async def test_malformed_alert_list_is_not_a_confirmed_zero(
    payload: dict[str, object],
) -> None:
    """Reject unusable responses rather than publishing a healthy zero count."""
    client = _cloud_client([payload])

    with pytest.raises(BrinkApiError, match="alert"):
        await client.async_get_active_alerts(101)


@pytest.mark.parametrize(
    ("summary", "expected_count"),
    [
        pytest.param(0, 0, id="flat_zero"),
        pytest.param(7, 7, id="flat_positive"),
        pytest.param({"alertCount": 0}, 0, id="nested_zero"),
        pytest.param({"alertCount": 7}, 7, id="nested_positive"),
    ],
)
async def test_valid_portal_summary_is_preserved(
    summary: object, expected_count: int
) -> None:
    """Normalize both portal summary formats without losing a valid zero."""
    client = _cloud_client([{"items": [_alert_payload(1), _alert_payload(2)]}])
    devices = await _fetch_devices(client, summary)
    assert devices[101].active_alert_count == expected_count
    assert type(devices[101].active_alert_count) is int


async def test_counts_belong_to_their_own_system() -> None:
    """Keep counts separate when the requested device is not first in the snapshot."""
    client = _cloud_client(
        [
            {"items": [_alert_payload(index) for index in range(3)]},
            {"items": [_alert_payload(0)]},
        ]
    )
    devices = await _fetch_devices(client, None, system_ids=(102, 101))
    coordinator = MagicMock(last_update_success=True, data=devices)

    assert devices[102].active_alert_count == 3
    assert _count_sensor(client, coordinator).native_value == 1


async def test_diagnostic_survives_a_blocking_device_alert() -> None:
    """Keep the diagnostic readable when a fault prevents device control."""
    blocking_alert = {**_alert_payload(1), "level": 3}
    client = _cloud_client([{"items": [blocking_alert]}])
    devices = await _fetch_devices(client, None)
    entity = _count_sensor(client, MagicMock(last_update_success=True, data=devices))

    assert devices[101].has_blocking_error is True
    assert entity.available is True
    assert entity.native_value == 1


@pytest.mark.usefixtures("enable_custom_integrations")
@pytest.mark.parametrize(
    ("summary", "expected_initial_state", "expected_recovered_state"),
    [
        pytest.param(None, "2", "0", id="missing_summary"),
        pytest.param({"alertCount": 0}, "0", "0", id="nested_zero"),
        pytest.param({"alertCount": 3}, "3", "3", id="nested_positive"),
    ],
)
async def test_sensor_state_fails_and_recovers_with_real_coordinator(
    hass: HomeAssistant,
    summary: object,
    expected_initial_state: str,
    expected_recovered_state: str,
) -> None:
    """Recover the valid portal summary or count alerts when it is missing."""
    client = _cloud_client([{"items": [_alert_payload(1), _alert_payload(2)]}])
    devices = await _fetch_devices(client, summary)
    entry = MockConfigEntry(domain=DOMAIN, data={})
    entry.add_to_hass(hass)
    coordinator = BrinkCoordinator(hass, entry, client, scan_interval=60)
    coordinator.async_set_updated_data(devices)
    entity = _count_sensor(client, coordinator)
    entity.entity_id = "sensor.synthetic_active_alerts"
    platform = EntityPlatform(
        hass=hass,
        logger=logging.getLogger(__name__),
        domain="sensor",
        platform_name=DOMAIN,
        platform=None,
        scan_interval=timedelta(seconds=60),
        entity_namespace=None,
    )
    platform.config_entry = entry
    try:
        await platform.async_add_entities([entity])
        initial_state = hass.states.get(entity.entity_id)
        assert initial_state is not None
        assert initial_state.state == expected_initial_state

        client.async_get_alerts.side_effect = BrinkApiError("Alert request failed")
        await coordinator.async_refresh()
        await hass.async_block_till_done()
        failed_state = hass.states.get(entity.entity_id)
        assert failed_state is not None
        assert failed_state.state == STATE_UNAVAILABLE

        client.async_get_alerts.side_effect = None
        client.async_get_alerts.return_value = {"items": []}
        await coordinator.async_refresh()
        await hass.async_block_till_done()
        recovered_state = hass.states.get(entity.entity_id)
        assert recovered_state is not None
        assert recovered_state.state == expected_recovered_state
    finally:
        await platform.async_reset()
        await coordinator.async_shutdown()


async def test_only_active_unarchived_alerts_are_counted() -> None:
    """Exclude inactive and archived records while traversing their pages."""
    inactive = [_alert_payload(index, is_active=False) for index in range(9)]
    archived = {**_alert_payload(10), "isArchived": True}
    client = _cloud_client(
        [
            {"items": [*inactive, _alert_payload(9)], "totalCount": 12},
            {"items": [archived, _alert_payload(11)], "totalCount": 12},
        ]
    )

    assert [alert.id for alert in await client.async_get_active_alerts(101)] == [9, 11]


async def test_pagination_without_a_total_fetches_a_terminal_empty_page() -> None:
    """Verify completeness when the last full page has no total metadata."""
    client = _cloud_client(
        [{"items": [_alert_payload(index) for index in range(10)]}, {"items": []}]
    )
    assert len(await client.async_get_active_alerts(101)) == 10
    assert client.async_get_alerts.await_count == 2


@pytest.mark.parametrize("total", [-1, True, 1.5, "12"])
async def test_invalid_pagination_totals_fail_safely(total: object) -> None:
    """Reject invalid totals without treating an empty list as a confirmed zero."""
    client = _cloud_client([{"items": [], "totalCount": total}])
    with pytest.raises(BrinkApiError, match="alert total"):
        await client.async_get_active_alerts(101)


@pytest.mark.parametrize(
    "pages",
    [
        [{"items": [_alert_payload(1)], "totalCount": 0}],
        [{"items": [_alert_payload(1)], "totalCount": 2}, {"items": []}],
        [
            {"items": [_alert_payload(1)], "totalCount": 2},
            {"items": [_alert_payload(2)], "totalCount": 3},
        ],
    ],
)
async def test_inconsistent_pages_are_not_a_partial_measurement(
    pages: list[dict[str, object]],
) -> None:
    """Retain a known total across pages and reject changing/truncated results."""
    client = _cloud_client(pages)
    with pytest.raises(BrinkApiError, match="alert"):
        await client.async_get_active_alerts(101)


@pytest.mark.parametrize(
    "record",
    [
        None,
        {},
        "invalid",
        {**_alert_payload(1), "id": True},
        {**_alert_payload(1), "id": -1},
        {**_alert_payload(1), "isActive": "false"},
        {**_alert_payload(1), "isArchived": None},
        {**_alert_payload(1), "incoming": "invalid"},
    ],
)
async def test_invalid_alert_record_does_not_reduce_the_count(record: object) -> None:
    """Reject bad records instead of dropping them and understating the count."""
    client = _cloud_client([{"items": [record]}])
    with pytest.raises(BrinkApiError, match="alert"):
        await client.async_get_active_alerts(101)


async def test_repeated_pages_stop_before_publishing_a_count() -> None:
    """Detect an endpoint that ignores the requested page index."""
    page = {"items": [_alert_payload(index) for index in range(10)]}
    client = _cloud_client([page, page])
    with pytest.raises(BrinkApiError, match="repeated an alert"):
        await client.async_get_active_alerts(101)
    assert client.async_get_alerts.await_count == 2


async def test_pagination_has_a_finite_request_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Bound requests if the endpoint never returns a terminal page."""
    monkeypatch.setattr(
        "custom_components.brink_ventilation.core.brink_home_cloud._MAX_ALERT_PAGES", 2
    )
    client = _cloud_client(
        [
            {"items": [_alert_payload(index) for index in range(10)]},
            {"items": [_alert_payload(index) for index in range(10, 20)]},
        ]
    )
    with pytest.raises(BrinkApiError, match="safe request limit"):
        await client.async_get_active_alerts(101)
    assert client.async_get_alerts.await_count == 2


@pytest.mark.parametrize("error_type", [BrinkApiError, CancelledError])
async def test_later_page_failure_never_publishes_a_partial_snapshot(
    error_type: type[BrinkApiError | CancelledError],
) -> None:
    """Propagate failed requests and cancellation after an earlier successful page."""
    client = _cloud_client([])
    failure = error_type("Alert fetch interrupted")
    client.async_get_alerts.side_effect = [
        {"items": [_alert_payload(index) for index in range(10)]},
        failure,
    ]

    with pytest.raises(error_type) as caught:
        await _fetch_devices(client, None)
    assert caught.value is failure


@pytest.mark.parametrize("page_index", [-1, True, "0", 1.5])
async def test_invalid_page_index_does_not_reach_the_api(page_index: object) -> None:
    """Reject invalid query values before contacting Brink."""
    client = BrinkHomeCloud(MagicMock(), "test-user", "test-password")
    client._api_request = AsyncMock()
    with pytest.raises(ValueError, match="non-negative integer"):
        await client.async_get_alerts(101, page_index=page_index)
    client._api_request.assert_not_awaited()


async def test_alert_page_request_preserves_filters_and_requested_index() -> None:
    """Pass pagination to the HTTP boundary without changing the archive filter."""
    client = BrinkHomeCloud(MagicMock(), "test-user", "test-password")
    response = MagicMock()
    response.json = AsyncMock(return_value={"items": []})
    client._api_request = AsyncMock(return_value=response)

    assert await client.async_get_alerts(101, page_index=2) == {"items": []}
    query = client._api_request.await_args.kwargs["params"]
    assert query["pageIndex"] == 2
    assert query["pageSize"] == 10
    assert query["filterSpecs[0].fieldName"] == "isArchived"
    assert query["filterSpecs[0].value"] == "false"


@pytest.mark.parametrize("payload", [None, [], "invalid"])
async def test_invalid_alert_response_object_is_rejected(payload: object) -> None:
    """Validate the decoded response before accessing alert collection fields."""
    client = BrinkHomeCloud(MagicMock(), "test-user", "test-password")
    response = MagicMock()
    response.json = AsyncMock(return_value=payload)
    client._api_request = AsyncMock(return_value=response)

    with pytest.raises(BrinkApiError, match="alert response object"):
        await client.async_get_alerts(101)
