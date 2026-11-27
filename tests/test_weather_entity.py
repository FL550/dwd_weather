"""Tests for weather entity."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.components.weather.const import WeatherEntityFeature
from homeassistant.const import (
    UnitOfLength,
    UnitOfPressure,
    UnitOfSpeed,
    UnitOfTemperature,
)

from custom_components.dwd_weather.const import ATTRIBUTION
from custom_components.dwd_weather.weather import DWDWeather
from .const import MOCK_CONFIG


@pytest.fixture
def weather_entity(hass_data):
    """Create weather entity with deterministic connector method outputs."""
    connector = hass_data["dwd_weather_data"]
    connector.get_condition = MagicMock(return_value="sunny")
    connector.get_temperature = MagicMock(return_value=12.3)
    connector.get_pressure = MagicMock(return_value=1012.4)
    connector.get_wind_speed = MagicMock(return_value=8.7)
    connector.get_wind_direction = MagicMock(return_value=180)
    connector.get_visibility = MagicMock(return_value=12.0)
    connector.get_humidity = MagicMock(return_value=65)
    connector.get_uv_index = MagicMock(return_value=3)
    connector.get_apparent_temperature = MagicMock(return_value=10.9)
    connector.get_airquality = MagicMock(return_value={"PM2_5": 12.0, "PM10": 20.0})
    connector.get_forecast = MagicMock(return_value=[{"condition": "sunny"}])
    connector.infos = {"station_id": "L732"}

    return DWDWeather(MOCK_CONFIG, hass_data)


def test_weather_unique_id_is_string(weather_entity):
    """Entity should expose a string unique_id."""
    assert isinstance(weather_entity.unique_id, str)


def test_weather_name_is_none_by_design(weather_entity):
    """name property is explicitly None in this integration."""
    assert weather_entity.name is None


def test_weather_supported_features(weather_entity):
    """Entity supports daily and hourly forecast APIs."""
    features = weather_entity.supported_features
    assert features & WeatherEntityFeature.FORECAST_DAILY
    assert features & WeatherEntityFeature.FORECAST_HOURLY


def test_weather_native_units(weather_entity):
    """Units should match integration declarations."""
    assert weather_entity.native_temperature_unit == UnitOfTemperature.CELSIUS
    assert weather_entity.native_pressure_unit == UnitOfPressure.HPA
    assert weather_entity.native_wind_speed_unit == UnitOfSpeed.KILOMETERS_PER_HOUR
    assert weather_entity.native_visibility_unit == UnitOfLength.KILOMETERS


def test_weather_value_properties(weather_entity):
    """Current condition values should come from connector methods."""
    assert weather_entity.condition == "sunny"
    assert weather_entity.native_temperature == 12.3
    assert weather_entity.native_pressure == 1012.4
    assert weather_entity.native_wind_speed == 8.7
    assert weather_entity.wind_bearing == 180
    assert weather_entity.native_visibility == 12.0
    assert weather_entity.humidity == 65
    assert weather_entity.uv_index == 3


def test_weather_attribution_and_extra_attributes(weather_entity):
    """Attribution and passthrough attributes should be available."""
    assert weather_entity.attribution == ATTRIBUTION
    assert weather_entity.extra_state_attributes == {
        "station_id": "L732",
    }


@pytest.mark.asyncio
async def test_weather_forecast_methods(weather_entity):
    """Forecast helper methods should call connector with proper feature flags."""
    daily = await weather_entity.async_forecast_daily()
    hourly = await weather_entity.async_forecast_hourly()

    assert daily == [{"condition": "sunny"}]
    assert hourly == [{"condition": "sunny"}]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("unit", "expected"),
    [(UnitOfLength.MILLIMETERS, (25.4, 50.8)), (UnitOfLength.INCHES, (1.0, 2.0))],
)
async def test_hourly_forecast_estimates_use_configured_unit(
    hass, weather_entity, unit, expected
):
    """Custom precipitation estimates use the weather entity's display unit."""
    weather_entity.hass = hass
    weather_entity._weather_option_precipitation_unit = unit
    native = [
        {
            "native_precipitation": 25.4,
            "precipitation_min": 25.4,
            "precipitation_max": 50.8,
        },
        {"precipitation_min": 0.0, "precipitation_max": None},
    ]
    weather_entity._connector.get_forecast.return_value = native

    hourly = await weather_entity.async_forecast_hourly()
    converted = weather_entity._convert_forecast(hourly)

    assert (
        converted[0]["precipitation_min"],
        converted[0]["precipitation_max"],
    ) == expected
    assert converted[0]["precipitation"] == expected[0]
    assert converted[1]["precipitation_min"] == 0.0
    assert converted[1]["precipitation_max"] is None
    weather_entity._weather_option_precipitation_unit = UnitOfLength.MILLIMETERS
    assert (await weather_entity.async_forecast_hourly())[0][
        "precipitation_max"
    ] == 50.8
    assert native[0]["precipitation_min"] == 25.4
    assert native[0]["precipitation_max"] == 50.8


@pytest.mark.asyncio
async def test_weather_async_update_requests_refresh(weather_entity):
    """Entity async_update should delegate to coordinator refresh."""
    weather_entity._coordinator.async_request_refresh = AsyncMock()

    await weather_entity.async_update()

    weather_entity._coordinator.async_request_refresh.assert_awaited_once()
