"""Tests for sensor entities."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.const import UnitOfTemperature

from custom_components.dwd_weather.sensor import (
    DWDWeatherForecastSensor,
    async_setup_entry,
)
from custom_components.dwd_weather.const import (
    CONF_DOWNLOAD_AIRQUALITY,
    ATTR_ISSUE_TIME,
    ATTR_LATEST_UPDATE,
    ATTR_STATION_ID,
    ATTR_STATION_NAME,
    DWDWEATHER_DATA,
)
from .const import MOCK_CONFIG


@pytest.fixture
def sensor_entity(hass_data):
    """Create a deterministic temperature sensor entity."""
    connector = hass_data[DWDWEATHER_DATA]
    connector.get_temperature = MagicMock(return_value=15.5)
    connector.get_temperature_hourly = MagicMock(return_value=[15.5, 16.0])
    connector.infos = {
        ATTR_ISSUE_TIME: "2026-01-01T00:00:00+00:00",
        ATTR_LATEST_UPDATE: "2026-01-01T00:01:00+00:00",
        ATTR_STATION_ID: "L732",
        ATTR_STATION_NAME: "Test Station",
    }
    connector.latest_update = "2026-01-01T00:01:00+00:00"

    return DWDWeatherForecastSensor(MOCK_CONFIG, hass_data, "temperature")


@pytest.mark.asyncio
async def test_sensor_setup_entry_callable():
    """Module should expose async_setup_entry for platform initialization."""
    assert async_setup_entry is not None


def test_sensor_unique_id_contains_station(sensor_entity):
    """Unique id should contain station id for stable identification."""
    assert "L732" in sensor_entity.unique_id


def test_sensor_state_and_unit(sensor_entity):
    """Temperature sensor should return connector value and configured unit."""
    assert sensor_entity.state == 15.5
    assert sensor_entity.unit_of_measurement == UnitOfTemperature.CELSIUS


def test_sensor_extra_attributes(sensor_entity):
    """Sensor should expose common metadata attributes."""
    attrs = sensor_entity.extra_state_attributes
    assert attrs[ATTR_STATION_ID] == "L732"
    assert attrs[ATTR_STATION_NAME] == "Test Station"
    assert ATTR_LATEST_UPDATE in attrs
    assert ATTR_ISSUE_TIME in attrs


def test_apparent_temperature_sensor_state_and_attributes(hass_data):
    """Apparent temperature sensor should expose value and hourly data."""
    connector = hass_data[DWDWEATHER_DATA]
    connector.get_apparent_temperature = MagicMock(return_value=13.2)
    connector.get_apparent_temperature_hourly = MagicMock(
        return_value=[{"value": 13.2}, {"value": 14.0}]
    )
    connector.infos = {
        ATTR_ISSUE_TIME: "2026-01-01T00:00:00+00:00",
        ATTR_LATEST_UPDATE: "2026-01-01T00:01:00+00:00",
        ATTR_STATION_ID: "L732",
        ATTR_STATION_NAME: "Test Station",
    }
    connector.latest_update = "2026-01-01T00:01:00+00:00"

    entity = DWDWeatherForecastSensor(MOCK_CONFIG, hass_data, "apparent_temperature")

    assert entity.state == 13.2
    attrs = entity.extra_state_attributes
    assert attrs["data"] == [{"value": 13.2}, {"value": 14.0}]


def test_sensor_available_reflects_latest_update(sensor_entity):
    """Sensor availability follows connector latest_update availability."""
    assert sensor_entity.available is True
    sensor_entity._connector.latest_update = None
    assert sensor_entity.available is False


def test_airquality_pm10_sensor_state_and_attributes(hass_data):
    """Airquality PM10 sensor should expose component state and hourly component data."""
    connector = hass_data[DWDWEATHER_DATA]
    connector._config[CONF_DOWNLOAD_AIRQUALITY] = True
    connector.get_airquality_component_state = MagicMock(return_value=20.0)
    connector.get_airquality_component_hourly = MagicMock(
        return_value=[{"value": 20.0}, {"value": 18.0}]
    )
    connector.infos = {
        ATTR_ISSUE_TIME: "2026-01-01T00:00:00+00:00",
        ATTR_LATEST_UPDATE: "2026-01-01T00:01:00+00:00",
        ATTR_STATION_ID: "L732",
        ATTR_STATION_NAME: "Test Station",
    }
    connector.latest_update = "2026-01-01T00:01:00+00:00"

    entity = DWDWeatherForecastSensor(MOCK_CONFIG, hass_data, "airquality_pm10")

    assert entity.state == 20.0
    connector.get_airquality_component_state.assert_called_once_with("PM10")
    attrs = entity.extra_state_attributes
    assert attrs["data"] == [
        {"value": 20.0},
        {"value": 18.0},
    ]
    connector.get_airquality_component_hourly.assert_called_once_with("PM10")


@pytest.mark.asyncio
async def test_sensor_async_update_requests_refresh(sensor_entity):
    """async_update should trigger coordinator refresh."""
    sensor_entity._coordinator.async_request_refresh = AsyncMock()

    await sensor_entity.async_update()

    sensor_entity._coordinator.async_request_refresh.assert_awaited_once()
