# pylint: disable=protected-access,redefined-outer-name
"""Tests for integration setup and unload."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.dwd_weather import (
    async_setup,
    async_setup_entry,
    async_unload_entry,
    update_listener,
)
from custom_components.dwd_weather.const import (
    CONF_ENTITY_TYPE,
    CONF_ENTITY_TYPE_MAP,
    CONF_ENTITY_TYPE_STATION,
    DOMAIN,
    DWDWEATHER_COORDINATOR,
    DWDWEATHER_DATA,
)
from .const import MOCK_CONFIG, MOCK_CONFIG_MAP, TEST_ENTRY_ID


@pytest.mark.asyncio
async def test_async_setup_returns_true(hass: HomeAssistant):
    """Integration async_setup should always return True."""
    assert await async_setup(hass, {DOMAIN: {}}) is True


@pytest.mark.asyncio
async def test_update_listener_triggers_reload(hass: HomeAssistant):
    """Options update listener should reload the config entry."""
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG, entry_id=TEST_ENTRY_ID)
    hass.config_entries.async_reload = AsyncMock()

    await update_listener(hass, entry)

    hass.config_entries.async_reload.assert_awaited_once_with(entry.entry_id)


@pytest.mark.asyncio
async def test_setup_entry_station_success(hass: HomeAssistant):
    """Station entry should initialize coordinator and store hass data."""
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG, entry_id=TEST_ENTRY_ID)

    with (
        patch("custom_components.dwd_weather.DWDWeatherData") as mock_data_cls,
        patch.object(
            hass.config_entries,
            "async_forward_entry_setups",
            AsyncMock(return_value=True),
        ) as mock_forward,
    ):
        mock_data = MagicMock()
        mock_data.async_initialize = AsyncMock()
        mock_data.async_update = AsyncMock()
        mock_data.dwd_weather.forecast_data = {"ok": {}}
        mock_data_cls.return_value = mock_data

        result = await async_setup_entry(hass, entry)

    assert result is True
    assert DOMAIN in hass.data
    assert entry.entry_id in hass.data[DOMAIN]
    assert DWDWEATHER_DATA in hass.data[DOMAIN][entry.entry_id]
    assert DWDWEATHER_COORDINATOR in hass.data[DOMAIN][entry.entry_id]
    assert mock_forward.await_count == 2


@pytest.mark.asyncio
async def test_setup_entry_station_raises_not_ready(hass: HomeAssistant):
    """Station entry should raise when initial forecast is missing."""
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG, entry_id=TEST_ENTRY_ID)

    with patch("custom_components.dwd_weather.DWDWeatherData") as mock_data_cls:
        mock_data = MagicMock()
        mock_data.async_initialize = AsyncMock()
        mock_data.async_update = AsyncMock()
        mock_data.dwd_weather.forecast_data = None
        mock_data.dwd_weather.issue_time = None
        mock_data_cls.return_value = mock_data

        with pytest.raises(ConfigEntryNotReady):
            await async_setup_entry(hass, entry)


@pytest.mark.asyncio
async def test_setup_entry_map_success(hass: HomeAssistant):
    """Map entry should initialize and forward camera platform."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={**MOCK_CONFIG_MAP, CONF_ENTITY_TYPE: CONF_ENTITY_TYPE_MAP},
        entry_id=TEST_ENTRY_ID,
    )

    with (
        patch("custom_components.dwd_weather.DWDMapData") as mock_map_cls,
        patch.object(
            hass.config_entries,
            "async_forward_entry_setups",
            AsyncMock(return_value=True),
        ) as mock_forward,
    ):
        mock_map = MagicMock()
        mock_map.async_update = AsyncMock()
        mock_map_cls.return_value = mock_map

        result = await async_setup_entry(hass, entry)

    assert result is True
    assert DOMAIN in hass.data
    assert entry.entry_id in hass.data[DOMAIN]
    mock_forward.assert_awaited_once_with(entry, ["camera"])


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "entity_type", [CONF_ENTITY_TYPE_STATION, CONF_ENTITY_TYPE_MAP]
)
async def test_setup_does_not_wait_for_initial_optional_data(hass, entity_type):
    """A slow optional station or map refresh must not hold setup open."""
    data = MOCK_CONFIG if entity_type == CONF_ENTITY_TYPE_STATION else MOCK_CONFIG_MAP
    entry = MockConfigEntry(domain=DOMAIN, data=data, entry_id=TEST_ENTRY_ID)
    started = asyncio.Event()
    release = asyncio.Event()
    finished = asyncio.Event()
    mock_data = MagicMock()
    mock_data.async_initialize = AsyncMock()
    mock_data.dwd_weather.forecast_data = None

    async def update():
        if entity_type == CONF_ENTITY_TYPE_STATION and (
            mock_data.dwd_weather.forecast_data is None
        ):
            mock_data.dwd_weather.forecast_data = {"ok": {}}
            return
        started.set()
        await release.wait()
        finished.set()

    mock_data.async_update = AsyncMock(side_effect=update)
    class_name = (
        "DWDWeatherData" if entity_type == CONF_ENTITY_TYPE_STATION else "DWDMapData"
    )
    with (
        patch(f"custom_components.dwd_weather.{class_name}", return_value=mock_data),
        patch.object(hass.config_entries, "async_forward_entry_setups", AsyncMock()),
    ):
        assert await asyncio.wait_for(async_setup_entry(hass, entry), timeout=1)
        await asyncio.wait_for(started.wait(), timeout=1)
        assert not finished.is_set()
        await asyncio.wait_for(hass.async_block_till_done(), timeout=1)
        assert not finished.is_set()
        release.set()
        await asyncio.wait_for(finished.wait(), timeout=1)
        await hass.data[DOMAIN][entry.entry_id][DWDWEATHER_COORDINATOR].async_shutdown()


@pytest.mark.asyncio
async def test_unloading_cancels_initial_map_refresh(hass):
    """Unloading an entry cancels its pending background refresh."""
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG_MAP, entry_id=TEST_ENTRY_ID)
    started = asyncio.Event()
    cancelled = asyncio.Event()

    async def update():
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.set()

    mock_map = MagicMock()
    mock_map.async_update = AsyncMock(side_effect=update)
    with (
        patch("custom_components.dwd_weather.DWDMapData", return_value=mock_map),
        patch.object(hass.config_entries, "async_forward_entry_setups", AsyncMock()),
    ):
        await async_setup_entry(hass, entry)
        await asyncio.wait_for(started.wait(), timeout=1)
        await entry._async_process_on_unload(hass)
        assert cancelled.is_set()


@pytest.mark.asyncio
async def test_unload_entry_station_success(hass: HomeAssistant):
    """Unload should remove entry data from hass for station entries."""
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG, entry_id=TEST_ENTRY_ID)
    hass.data[DOMAIN] = {
        entry.entry_id: {
            DWDWEATHER_DATA: MagicMock(),
            DWDWEATHER_COORDINATOR: MagicMock(),
        }
    }

    with patch.object(
        hass.config_entries,
        "async_forward_entry_unload",
        AsyncMock(return_value=True),
    ):
        result = await async_unload_entry(hass, entry)

    assert result is True
    assert DOMAIN not in hass.data
