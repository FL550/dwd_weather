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


@pytest.mark.asyncio
async def test_connector_initializes_airquality_clients_when_enabled(
    hass: HomeAssistant, mock_dwd_weather_object
):
    """Air quality clients should be created during connector initialization."""
    entry = MagicMock()
    entry.data = {**MOCK_CONFIG, "download_airquality": True}

    with (
        patch(
            "custom_components.dwd_weather.connector.dwdforecast.Weather",
            return_value=mock_dwd_weather_object,
        ),
        patch("custom_components.dwd_weather.connector.AirQuality") as mock_airquality,
    ):
        hourly_client = MagicMock()
        hourly_client.station_id = "station-1"
        daily_client = MagicMock()
        mock_airquality.get_station_from_location.return_value = hourly_client
        mock_airquality.return_value = daily_client

        data = DWDWeatherData(hass, entry)

    assert data._airquality_hourly is hourly_client
    assert data._airquality_daily is daily_client
    mock_airquality.get_station_from_location.assert_called_once()
    mock_airquality.assert_called_once_with("station-1", "daily")


def test_get_airquality_uses_hourly_when_requested(mock_dwd_data):
    """Air quality getter should return hourly current value for hourly forecast."""
    mock_dwd_data._config["download_airquality"] = True
    mock_dwd_data._airquality_hourly = MagicMock()
    mock_dwd_data._airquality_hourly.data = [{"PM2_5": 11.0}, {"PM2_5": 9.0}]

    result = mock_dwd_data.get_airquality(WeatherEntityFeature.FORECAST_HOURLY)

    assert result == {"PM2_5": 11.0}


def test_get_airquality_uses_daily_when_requested(mock_dwd_data):
    """Air quality getter should return today's value for daily forecast."""
    mock_dwd_data._config["download_airquality"] = True
    mock_dwd_data._airquality_daily = MagicMock()
    mock_dwd_data._airquality_daily.data = {
        "today": {"PM2_5": 20.0},
        "tomorrow": {"PM2_5": 15.0},
        "day_after": {"PM2_5": 12.0},
    }

    result = mock_dwd_data.get_airquality(WeatherEntityFeature.FORECAST_DAILY)

    assert result == {"PM2_5": 20.0}


def test_update_does_not_download_airquality_when_disabled(mock_dwd_data):
    """Air quality updates should not run when air quality is not enabled."""
    mock_dwd_data._config["download_airquality"] = False
    mock_dwd_data.latest_update = None
    mock_dwd_data._airquality_hourly = MagicMock()
    mock_dwd_data._airquality_daily = MagicMock()

    assert mock_dwd_data._update() is True
    mock_dwd_data._airquality_hourly.update.assert_not_called()
    mock_dwd_data._airquality_daily.update.assert_not_called()


def test_update_downloads_airquality_when_enabled(mock_dwd_data):
    """Air quality clients should be updated during _update when enabled."""
    mock_dwd_data._config["download_airquality"] = True
    mock_dwd_data.latest_update = None
    hourly_client = MagicMock()
    daily_client = MagicMock()
    mock_dwd_data._airquality_hourly = hourly_client
    mock_dwd_data._airquality_daily = daily_client

    assert mock_dwd_data._update() is True

    hourly_client.update.assert_called_once_with()
    daily_client.update.assert_called_once_with(with_current_day=True)


def _setup_forecast_weather_mocks(mock_dwd_data):
    """Configure deterministic weather mock return values for forecast methods."""
    dwd_weather = mock_dwd_data.dwd_weather
    dwd_weather.is_in_timerange = MagicMock(return_value=True)
    dwd_weather.get_timeframe_condition = MagicMock(return_value="sunny")
    dwd_weather.get_timeframe_max = MagicMock(return_value=280.0)
    dwd_weather.get_timeframe_min = MagicMock(return_value=278.0)
    dwd_weather.get_timeframe_sum = MagicMock(return_value=1.0)
    dwd_weather.get_timeframe_avg = MagicMock(return_value=180.0)
    dwd_weather.get_daily_condition = MagicMock(return_value="sunny")
    dwd_weather.get_daily_max = MagicMock(return_value=280.0)
    dwd_weather.get_daily_min = MagicMock(return_value=278.0)
    dwd_weather.get_daily_avg = MagicMock(return_value=180.0)
    dwd_weather.get_daily_sum = MagicMock(return_value=1.0)
    dwd_weather.get_uv_index = MagicMock(return_value=2)


def test_hourly_forecast_includes_airquality_when_both_options_enabled(mock_dwd_data):
    """Hourly forecast should include air quality fields only when both toggles are enabled."""
    _setup_forecast_weather_mocks(mock_dwd_data)

    mock_dwd_data._config["additional_forecast_attributes"] = True
    mock_dwd_data._config["download_airquality"] = True
    mock_dwd_data._airquality_hourly = MagicMock()
    mock_dwd_data._airquality_hourly.data = [
        {
            "Stickstoffdioxid": 21.0,
            "Ozon": 34.0,
            "PM2_5": 12.0,
            "PM10": 19.0,
        }
    ]

    result = mock_dwd_data.get_forecast_hourly()

    assert result is not None
    assert result[0]["airquality_stickstoffdioxid"] == 21.0
    assert result[0]["airquality_ozon"] == 34.0
    assert result[0]["airquality_pm2_5"] == 12.0
    assert result[0]["airquality_pm10"] == 19.0


def test_hourly_forecast_does_not_include_airquality_when_additional_attrs_disabled(
    mock_dwd_data,
):
    """Hourly forecast should omit air quality fields when additional attrs are disabled."""
    _setup_forecast_weather_mocks(mock_dwd_data)

    mock_dwd_data._config["additional_forecast_attributes"] = False
    mock_dwd_data._config["download_airquality"] = True
    mock_dwd_data._airquality_hourly = MagicMock()
    mock_dwd_data._airquality_hourly.data = [{"PM2_5": 12.0}]

    result = mock_dwd_data.get_forecast_hourly()

    assert result is not None
    assert "airquality_pm2_5" not in result[0]


def test_get_apparent_temperature_returns_none_when_not_supported(mock_dwd_data):
    """Apparent temperature should be unavailable when the feature is unsupported."""
    mock_dwd_data._config["download_apparent_temperature"] = True
    mock_dwd_data.dwd_weather.supports_apparent_temperature = MagicMock(
        return_value=False
    )

    result = mock_dwd_data.get_apparent_temperature()

    assert result is None
    mock_dwd_data.dwd_weather.get_apparent_temperature.assert_not_called()


def test_get_apparent_temperature_hourly_returns_empty_when_not_supported(
    mock_dwd_data,
):
    """Hourly apparent temperature list should be empty when unsupported."""
    mock_dwd_data._config["download_apparent_temperature"] = True
    mock_dwd_data.dwd_weather.supports_apparent_temperature = MagicMock(
        return_value=False
    )

    result = mock_dwd_data.get_apparent_temperature_hourly()

    assert result == []
    mock_dwd_data.dwd_weather.get_apparent_temperature_forecast.assert_not_called()
