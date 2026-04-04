# pylint: disable=protected-access,redefined-outer-name
"""Global fixtures for integration."""

from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from collections import OrderedDict

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.dwd_weather.connector import DWDWeatherData, DWDMapData
from custom_components.dwd_weather.sensor import DWDWeatherForecastSensor
from custom_components.dwd_weather.const import (
    DOMAIN,
    DWDWEATHER_DATA,
    DWDWEATHER_COORDINATOR,
    CONF_STATION_ID,
    CONF_ENTITY_TYPE,
    CONF_ENTITY_TYPE_STATION,
    CONF_DATA_TYPE_FORECAST,
    ATTR_LATEST_UPDATE,
    ATTR_ISSUE_TIME,
)

pytest_plugins = "pytest_homeassistant_custom_component"  # pylint: disable=invalid-name


# ============================================================================
# Auto-use Fixtures (applied to all tests)
# ============================================================================


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Automatically enable loading custom integrations in all tests."""
    yield


@pytest.fixture(name="skip_notifications", autouse=True)
def skip_notifications_fixture():
    """Skip notification calls."""
    with patch("homeassistant.components.persistent_notification.async_create"), patch(
        "homeassistant.components.persistent_notification.async_dismiss"
    ):
        yield


# ============================================================================
# Mock Data Fixtures
# ============================================================================


@pytest.fixture(name="mock_forecast_data")
def mock_forecast_data_fixture():
    """Create mock hourly forecast data matching simple_dwd_weatherforecast structure."""
    return OrderedDict(
        {
            "2024-01-15T12:00:00.000Z": {
                "weather_icon": 1,
                "condition": "sunny",
                "temperature": 5.0,
                "dewpoint": -2.0,
                "wind_direction": 270,
                "wind_speed": 3.5,
                "wind_gust": 6.2,
                "precipitation": 0.0,
                "precipitation_probability": 0,
                "cloud_coverage": 10,
                "pressure": 1013.25,
                "visibility": 10000,
                "sun_duration": 50,
                "sun_irradiance": 120,
                "fog_probability": 5,
                "dew_point": -2.0,
                "humidity": 65,
                "humidity_absolute": 3.2,
                "evaporation": 0.1,
                "precipitation_duration": 0,
            },
            "2024-01-15T13:00:00.000Z": {
                "weather_icon": 2,
                "condition": "partly cloudy",
                "temperature": 6.5,
                "dewpoint": -1.0,
                "wind_direction": 260,
                "wind_speed": 4.2,
                "wind_gust": 7.1,
                "precipitation": 0.0,
                "precipitation_probability": 5,
                "cloud_coverage": 30,
                "pressure": 1013.20,
                "visibility": 10000,
                "sun_duration": 45,
                "sun_irradiance": 150,
                "fog_probability": 3,
                "humidity": 60,
                "humidity_absolute": 3.5,
                "evaporation": 0.15,
                "precipitation_duration": 0,
            },
            "2024-01-15T14:00:00.000Z": {
                "weather_icon": 3,
                "condition": "cloudy",
                "temperature": 7.0,
                "dewpoint": 0.0,
                "wind_direction": 250,
                "wind_speed": 5.0,
                "wind_gust": 8.5,
                "precipitation": 1.2,
                "precipitation_probability": 40,
                "cloud_coverage": 60,
                "pressure": 1013.10,
                "visibility": 8000,
                "sun_duration": 20,
                "sun_irradiance": 100,
                "fog_probability": 10,
                "humidity": 70,
                "humidity_absolute": 4.0,
                "evaporation": 0.2,
                "precipitation_duration": 30,
            },
        }
    )


@pytest.fixture(name="mock_dwd_weather_object")
def mock_dwd_weather_object_fixture(mock_forecast_data):
    """Create a mock DWD Weather object."""
    mock_weather = MagicMock()
    mock_weather.station_id = "L732"
    mock_weather.station = {
        "id": "L732",
        "name": "Test Station",
        "lat": 52.5,
        "lon": 13.4,
        "elev": 34,
    }
    mock_weather.forecast_data = mock_forecast_data
    mock_weather.issue_time = "2024-01-15T12:00:00+00:00"
    mock_weather.report_data = None
    mock_weather.get_weather_report = MagicMock(return_value="Test weather report")
    mock_weather.update = MagicMock()
    mock_weather.is_in_timerange = MagicMock(return_value=True)
    mock_weather.strip_to_hour_str = MagicMock(return_value="2024-01-15T12:00:00.000Z")
    return mock_weather


# ============================================================================
# Data Connector Fixtures
# ============================================================================


@pytest.fixture(name="mock_dwd_data")
def mock_dwd_data_fixture(hass, mock_dwd_weather_object):
    """Create a mock DWDWeatherData instance."""
    mock_config_entry = MagicMock()
    mock_config_entry.data = {
        CONF_STATION_ID: "L732",
        "station_name": "Test Station",
        "latitude": 52.5,
        "longitude": 13.4,
        "hourly_update": False,
        "download_airquality": False,
        "download_apparent_temperature": False,
        "data_type": CONF_DATA_TYPE_FORECAST,
        "interpolate": True,
        "daily_temp_high_precision": False,
        "additional_forecast_attributes": True,
        "sensor_forecast_steps": 5,
        "wind_direction_type": "degrees",
    }

    with patch(
        "custom_components.dwd_weather.connector.dwdforecast.Weather"
    ) as mock_weather_class:
        mock_weather_class.return_value = mock_dwd_weather_object
        dwd_data = DWDWeatherData(hass, mock_config_entry)
        dwd_data.dwd_weather = mock_dwd_weather_object
        dwd_data.latest_update = datetime.now(timezone.utc)
        dwd_data.infos = {
            ATTR_LATEST_UPDATE: datetime.now(timezone.utc),
            ATTR_ISSUE_TIME: "2024-01-15T12:00:00+00:00",
        }
    return dwd_data


@pytest.fixture(name="mock_coordinator")
def mock_coordinator_fixture():
    """Create a mock DataUpdateCoordinator."""
    mock_coord = MagicMock()
    mock_coord.data = None
    mock_coord.last_update_success = True
    mock_coord.async_request_refresh = AsyncMock()
    mock_coord.async_add_listener = MagicMock(return_value=lambda: None)
    return mock_coord


# ============================================================================
# Bypass/Error Fixtures
# ============================================================================


@pytest.fixture(name="bypass_get_data")
def bypass_get_data_fixture():
    """Skip calls to async_update."""
    with patch.object(DWDWeatherData, "async_update", new_callable=AsyncMock):
        yield


@pytest.fixture(name="error_on_get_data")
def error_get_data_fixture():
    """Simulate error when retrieving data from API."""
    with patch.object(
        DWDWeatherData, "async_update", side_effect=Exception("API Error")
    ):
        yield


# ============================================================================
# Setup Fixtures
# ============================================================================


@pytest.fixture(name="hass_data")
def hass_data_fixture(mock_dwd_data, mock_coordinator):
    """Create mock hass data structure."""
    return {
        DWDWEATHER_DATA: mock_dwd_data,
        DWDWEATHER_COORDINATOR: mock_coordinator,
    }


@pytest.fixture(name="setup_integration")
async def setup_integration_fixture(hass, mock_dwd_data, mock_coordinator):
    """Set up the integration for testing."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_ENTITY_TYPE: CONF_ENTITY_TYPE_STATION,
            CONF_STATION_ID: "L732",
            "station_name": "Test Station",
            "latitude": 52.5,
            "longitude": 13.4,
        },
        entry_id="test_entry",
    )

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][config_entry.entry_id] = {
        DWDWEATHER_DATA: mock_dwd_data,
        DWDWEATHER_COORDINATOR: mock_coordinator,
    }

    return config_entry
