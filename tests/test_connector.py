"""Tests for connector data object."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.components.weather import WeatherEntityFeature
from homeassistant.core import HomeAssistant

from custom_components.dwd_weather.connector import DWDWeatherData
from custom_components.dwd_weather.const import CONF_STATION_ID
from .const import MOCK_CONFIG


@pytest.mark.asyncio
async def test_connector_initializes_with_config(
    hass: HomeAssistant, mock_dwd_weather_object
):
    """Connector should keep config and start with empty entity list."""
    entry = MagicMock()
    entry.data = MOCK_CONFIG

    with patch(
        "custom_components.dwd_weather.connector.dwdforecast.Weather",
        return_value=mock_dwd_weather_object,
    ):
        data = DWDWeatherData(hass, entry)

    assert data._config[CONF_STATION_ID] == MOCK_CONFIG[CONF_STATION_ID]
    assert data.entities == []


@pytest.mark.asyncio
async def test_connector_register_entity_appends_list(
    hass: HomeAssistant, mock_dwd_data
):
    """register_entity should append entity instances."""
    entity = MagicMock()

    mock_dwd_data.register_entity(entity)

    assert entity in mock_dwd_data.entities


@pytest.mark.asyncio
async def test_async_update_notifies_registered_entities(
    hass: HomeAssistant, mock_dwd_data
):
    """async_update should notify listeners when update succeeds."""
    entity = MagicMock()
    entity.async_update_listeners = AsyncMock()
    mock_dwd_data.register_entity(entity)

    mock_dwd_data._update = MagicMock(return_value=True)

    await mock_dwd_data.async_update()

    entity.async_update_listeners.assert_awaited_once()


@pytest.mark.asyncio
async def test_async_update_does_not_notify_when_update_returns_false(mock_dwd_data):
    """No entity listener update should fire when _update returns False."""
    entity = MagicMock()
    entity.async_update_listeners = AsyncMock()
    mock_dwd_data.register_entity(entity)
    mock_dwd_data._update = MagicMock(return_value=False)

    await mock_dwd_data.async_update()

    entity.async_update_listeners.assert_not_awaited()


@pytest.mark.asyncio
async def test_get_forecast_dispatches_to_daily(mock_dwd_data):
    """get_forecast should route daily requests to get_forecast_daily."""
    mock_dwd_data.get_forecast_daily = MagicMock(return_value=[{"ok": "daily"}])

    result = mock_dwd_data.get_forecast(WeatherEntityFeature.FORECAST_DAILY)

    assert result == [{"ok": "daily"}]


@pytest.mark.asyncio
async def test_get_forecast_dispatches_to_hourly(mock_dwd_data):
    """get_forecast should route hourly requests to get_forecast_hourly."""
    mock_dwd_data.get_forecast_hourly = MagicMock(return_value=[{"ok": "hourly"}])

    result = mock_dwd_data.get_forecast(WeatherEntityFeature.FORECAST_HOURLY)

    assert result == [{"ok": "hourly"}]


@pytest.mark.asyncio
async def test_update_returns_false_when_refresh_not_due(mock_dwd_data):
    """_update should short-circuit when minute is not refresh boundary."""
    mock_dwd_data.latest_update = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)

    with patch("custom_components.dwd_weather.connector.datetime") as mock_datetime:
        mock_datetime.now.return_value = datetime(
            2026, 1, 1, 12, 1, tzinfo=timezone.utc
        )

        assert mock_dwd_data._update() is False


def test_mock_config_contains_required_keys():
    """Sanity-check minimal config shape required by connector."""
    for key in ("station_id", "station_name", "data_type"):
        assert key in MOCK_CONFIG
