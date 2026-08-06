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
async def test_connector_does_not_initialize_airquality_clients_while_disabled(
    hass: HomeAssistant, mock_dwd_weather_object
):
    """Air quality clients stay uninitialized while upstream endpoint is unavailable."""
    entry = MagicMock()
    entry.data = {**MOCK_CONFIG, "download_airquality": True}

    with (
        patch(
            "custom_components.dwd_weather.connector.dwdforecast.Weather",
            return_value=mock_dwd_weather_object,
        ),
    ):
        data = DWDWeatherData(hass, entry)
        data._update = MagicMock(return_value=False)
        await data.async_update()

    assert data._airquality_hourly is None
    assert data._airquality_daily is None


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


def test_update_does_not_download_airquality_when_enabled_temporarily_disabled(
    mock_dwd_data,
):
    """Air quality clients should not be updated while endpoint is unavailable."""
    mock_dwd_data._config["download_airquality"] = True
    mock_dwd_data.latest_update = None
    hourly_client = MagicMock()
    daily_client = MagicMock()
    mock_dwd_data._airquality_hourly = hourly_client
    mock_dwd_data._airquality_daily = daily_client

    assert mock_dwd_data._update() is True

    hourly_client.update.assert_not_called()
    daily_client.update.assert_not_called()


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


def test_update_refreshes_radar_precipitation_only_when_enabled(mock_dwd_data):
    """Radar precipitation methods should be called during _update only when enabled."""
    mock_dwd_data._config["download_precipitation_sensors"] = True
    mock_dwd_data.latest_update = None
    mock_dwd_data.dwd_weather.get_radar_precipitation_forecast = MagicMock(
        return_value={}
    )
    mock_dwd_data.dwd_weather.get_radar_next_precipitation = MagicMock(return_value={})

    assert mock_dwd_data._update() is True

    mock_dwd_data.dwd_weather.get_radar_precipitation_forecast.assert_called_once_with(
        shouldUpdate=True
    )
    mock_dwd_data.dwd_weather.get_radar_next_precipitation.assert_called_once_with(
        shouldUpdate=False
    )


def test_update_skips_radar_precipitation_when_disabled(mock_dwd_data):
    """Radar precipitation methods should not be called when feature toggle is disabled."""
    mock_dwd_data._config["download_precipitation_sensors"] = False
    mock_dwd_data.latest_update = None
    mock_dwd_data.dwd_weather.get_radar_precipitation_forecast = MagicMock(
        return_value={}
    )
    mock_dwd_data.dwd_weather.get_radar_next_precipitation = MagicMock(return_value={})

    assert mock_dwd_data._update() is True

    mock_dwd_data.dwd_weather.get_radar_precipitation_forecast.assert_not_called()
    mock_dwd_data.dwd_weather.get_radar_next_precipitation.assert_not_called()


def test_radar_getters_do_not_trigger_refresh_calls(mock_dwd_data):
    """Radar getters should only read cached update data and never trigger downloads."""
    mock_dwd_data._radar_precipitation_forecast = {
        datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc): 0.0,
        datetime(2026, 1, 1, 0, 5, tzinfo=timezone.utc): 1.2,
    }
    mock_dwd_data._radar_next_precipitation = {
        "start": datetime(2026, 1, 1, 0, 5, tzinfo=timezone.utc),
        "end": datetime(2026, 1, 1, 0, 15, tzinfo=timezone.utc),
        "max": 3.6,
        "sum": 0.9,
        "length": datetime(2026, 1, 1, 0, 10, tzinfo=timezone.utc)
        - datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc),
    }
    mock_dwd_data.dwd_weather.get_radar_precipitation_forecast = MagicMock()
    mock_dwd_data.dwd_weather.get_radar_next_precipitation = MagicMock()

    start = mock_dwd_data.get_radar_next_precipitation_start()
    assert start == "2026-01-01T00:05:00+00:00"
    attrs = mock_dwd_data.get_radar_next_precipitation_attributes()
    assert attrs["end"] == "2026-01-01T00:15:00+00:00"
    assert attrs["length"] == 10
    assert attrs["max"] == 3.6
    assert attrs["sum"] == 0.9
    assert len(mock_dwd_data.get_radar_precipitation_hourly()) == 2

    mock_dwd_data.dwd_weather.get_radar_precipitation_forecast.assert_not_called()
    mock_dwd_data.dwd_weather.get_radar_next_precipitation.assert_not_called()


def test_get_radar_precipitation_hourly_respects_forecast_steps(mock_dwd_data):
    """get_radar_precipitation_hourly should limit results to CONF_SENSOR_FORECAST_STEPS."""
    # Setup radar precipitation forecast with 5 data points
    mock_dwd_data._radar_precipitation_forecast = {
        datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc): 0.0,
        datetime(2026, 1, 1, 0, 5, tzinfo=timezone.utc): 1.2,
        datetime(2026, 1, 1, 0, 10, tzinfo=timezone.utc): 2.4,
        datetime(2026, 1, 1, 0, 15, tzinfo=timezone.utc): 1.8,
        datetime(2026, 1, 1, 0, 20, tzinfo=timezone.utc): 0.6,
    }

    # Test with CONF_SENSOR_FORECAST_STEPS = 5 (should return all)
    result = mock_dwd_data.get_radar_precipitation_hourly()
    assert len(result) == 5

    # Test with CONF_SENSOR_FORECAST_STEPS = 2 (should return only first 2)
    mock_dwd_data._config["sensor_forecast_steps"] = 2
    result = mock_dwd_data.get_radar_precipitation_hourly()
    assert len(result) == 2
    assert result[0]["value"] == 0.0
    assert result[1]["value"] == 1.2

    # Test with CONF_SENSOR_FORECAST_STEPS = 0 (should return all)
    mock_dwd_data._config["sensor_forecast_steps"] = 0
    result = mock_dwd_data.get_radar_precipitation_hourly()
    assert len(result) == 5


def test_get_airquality_hourly_respects_forecast_steps(mock_dwd_data):
    """get_airquality_hourly should limit results based on CONF_SENSOR_FORECAST_STEPS."""
    from homeassistant.components.weather import WeatherEntityFeature

    # Create mock airquality data with 5 items
    mock_airquality_data = [
        {"PM2_5": 10.0, "PM10": 20.0},
        {"PM2_5": 11.0, "PM10": 21.0},
        {"PM2_5": 12.0, "PM10": 22.0},
        {"PM2_5": 13.0, "PM10": 23.0},
        {"PM2_5": 14.0, "PM10": 24.0},
    ]

    # Mock the airquality data source
    mock_dwd_data._airquality_hourly = MagicMock()
    mock_dwd_data._airquality_hourly.data = mock_airquality_data
    mock_dwd_data._config["download_airquality"] = True

    # Test with CONF_SENSOR_FORECAST_STEPS = 5 (should return all)
    result = mock_dwd_data.get_airquality_hourly()
    assert len(result) == 5

    # Test with CONF_SENSOR_FORECAST_STEPS = 2 (should return only first 2)
    mock_dwd_data._config["sensor_forecast_steps"] = 2
    result = mock_dwd_data.get_airquality_hourly()
    assert len(result) == 2
    assert result[0]["value"]["PM2_5"] == 10.0
    assert result[1]["value"]["PM2_5"] == 11.0

    # Test with CONF_SENSOR_FORECAST_STEPS = 0 (should return all)
    mock_dwd_data._config["sensor_forecast_steps"] = 0
    result = mock_dwd_data.get_airquality_hourly()
    assert len(result) == 5


def test_get_radar_precipitation_hourly_with_integer_forecast_steps(mock_dwd_data):
    """get_radar_precipitation_hourly should convert forecast_steps to int for slicing."""
    mock_dwd_data._radar_precipitation_forecast = {
        datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc): 0.1,
        datetime(2026, 1, 1, 0, 5, tzinfo=timezone.utc): 0.2,
        datetime(2026, 1, 1, 0, 10, tzinfo=timezone.utc): 0.3,
    }

    # Simulate the config value being a string (from config flow)
    # This should not cause a TypeError
    mock_dwd_data._config["sensor_forecast_steps"] = "2"
    result = mock_dwd_data.get_radar_precipitation_hourly()
    assert len(result) == 2
    assert result[0]["value"] == 0.1
    assert result[1]["value"] == 0.2


def test_get_airquality_hourly_with_integer_forecast_steps(mock_dwd_data):
    """get_airquality_hourly should convert forecast_steps to int for comparisons."""
    from homeassistant.components.weather import WeatherEntityFeature

    # Create mock airquality data with 3 items
    mock_airquality_data = [
        {"PM2_5": 10.0, "PM10": 20.0},
        {"PM2_5": 11.0, "PM10": 21.0},
        {"PM2_5": 12.0, "PM10": 22.0},
    ]

    # Mock the airquality data source
    mock_dwd_data._airquality_hourly = MagicMock()
    mock_dwd_data._airquality_hourly.data = mock_airquality_data
    mock_dwd_data._config["download_airquality"] = True

    # Simulate the config value being a string (from config flow)
    # This should not cause a TypeError
    mock_dwd_data._config["sensor_forecast_steps"] = "2"
    result = mock_dwd_data.get_airquality_hourly()
    assert len(result) == 2
    assert result[0]["value"]["PM2_5"] == 10.0
    assert result[1]["value"]["PM2_5"] == 11.0


def test_update_radar_precipitation_uses_station_coords_by_default(mock_dwd_data):
    """Radar precipitation update should use station coordinates when custom location is disabled."""
    mock_dwd_data._config["download_precipitation_sensors"] = True
    mock_dwd_data._config["radar_custom_location"] = False

    mock_dwd_data.dwd_weather.get_radar_precipitation_forecast = MagicMock(
        return_value={}
    )
    mock_dwd_data.dwd_weather.get_radar_next_precipitation = MagicMock(return_value={})

    mock_dwd_data._update_radar_precipitation()

    mock_dwd_data.dwd_weather.get_radar_precipitation_forecast.assert_called_once_with(
        shouldUpdate=True
    )
    mock_dwd_data.dwd_weather.get_radar_next_precipitation.assert_called_once_with(
        shouldUpdate=False
    )


def test_update_radar_precipitation_uses_custom_coords_when_enabled(mock_dwd_data):
    """Radar precipitation update should pass custom coordinates when toggle is enabled."""
    mock_dwd_data._config["download_precipitation_sensors"] = True
    mock_dwd_data._config["radar_custom_location"] = True
    mock_dwd_data._config["radar_location_coordinates"] = {
        "latitude": 48.1,
        "longitude": 11.6,
    }

    mock_dwd_data.dwd_weather.get_radar_precipitation_forecast = MagicMock(
        return_value={}
    )
    mock_dwd_data.dwd_weather.get_radar_next_precipitation = MagicMock(return_value={})

    mock_dwd_data._update_radar_precipitation()

    mock_dwd_data.dwd_weather.get_radar_precipitation_forecast.assert_called_once_with(
        shouldUpdate=True, lat=48.1, lon=11.6
    )
    mock_dwd_data.dwd_weather.get_radar_next_precipitation.assert_called_once_with(
        shouldUpdate=False, lat=48.1, lon=11.6
    )


def test_update_radar_precipitation_falls_back_to_station_when_coords_missing(
    mock_dwd_data,
):
    """Radar precipitation update should fall back to station coords when custom coords are absent."""
    mock_dwd_data._config["download_precipitation_sensors"] = True
    mock_dwd_data._config["radar_custom_location"] = True
    mock_dwd_data._config["radar_location_coordinates"] = {}

    mock_dwd_data.dwd_weather.get_radar_precipitation_forecast = MagicMock(
        return_value={}
    )
    mock_dwd_data.dwd_weather.get_radar_next_precipitation = MagicMock(return_value={})

    mock_dwd_data._update_radar_precipitation()

    mock_dwd_data.dwd_weather.get_radar_precipitation_forecast.assert_called_once_with(
        shouldUpdate=True
    )
    mock_dwd_data.dwd_weather.get_radar_next_precipitation.assert_called_once_with(
        shouldUpdate=False
    )
