# pylint: disable=protected-access,redefined-outer-name
"""Tests for integration setup and unload."""

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
