"""Constants for tests."""

from typing import Final
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE, CONF_NAME
from custom_components.dwd_weather.const import (
    DEFAULT_WIND_DIRECTION_TYPE,
    CONF_WIND_DIRECTION_TYPE,
    CONF_STATION_ID,
    CONF_STATION_NAME,
    CONF_ENTITY_TYPE,
    CONF_ENTITY_TYPE_STATION,
    CONF_ENTITY_TYPE_MAP,
    CONF_DATA_TYPE,
    CONF_DATA_TYPE_FORECAST,
    CONF_DATA_TYPE_REPORT,
    CONF_DATA_TYPE_MIXED,
    CONF_HOURLY_UPDATE,
    CONF_DOWNLOAD_AIRQUALITY,
    CONF_DOWNLOAD_APPARENT_TEMPERATURE,
    CONF_DOWNLOAD_PRECIPITATION_SENSORS,
    CONF_INTERPOLATE,
    CONF_DAILY_TEMP_HIGH_PRECISION,
    CONF_ADDITIONAL_FORECAST_ATTRIBUTES,
    CONF_SENSOR_FORECAST_STEPS,
    CONF_MAP_TYPE,
    CONF_MAP_TYPE_GERMANY,
    CONF_MAP_HOMEMARKER,
    CONF_MAP_CENTERMARKER,
    CONF_MAP_DARK_MODE,
)

# ============================================================================
# Station Configuration Mock Data
# ============================================================================

MOCK_CONFIG: Final = {
    CONF_ENTITY_TYPE: CONF_ENTITY_TYPE_STATION,
    CONF_LATITUDE: 52.5,
    CONF_LONGITUDE: 13.4,
    CONF_NAME: "Test Station",
    CONF_STATION_ID: "L732",
    CONF_STATION_NAME: "Berlin Tegel",
    CONF_WIND_DIRECTION_TYPE: DEFAULT_WIND_DIRECTION_TYPE,
    CONF_DATA_TYPE: CONF_DATA_TYPE_FORECAST,
    CONF_HOURLY_UPDATE: False,
    CONF_DOWNLOAD_AIRQUALITY: False,
    CONF_DOWNLOAD_APPARENT_TEMPERATURE: False,
    CONF_DOWNLOAD_PRECIPITATION_SENSORS: False,
    CONF_INTERPOLATE: True,
    CONF_DAILY_TEMP_HIGH_PRECISION: False,
    CONF_ADDITIONAL_FORECAST_ATTRIBUTES: True,
    CONF_SENSOR_FORECAST_STEPS: 5,
}

MOCK_USER_INPUT: Final = {
    CONF_STATION_ID: "L732",
}

# ============================================================================
# Config Flow Test Scenarios
# ============================================================================

MOCK_CONFIG_FORECAST: Final = {
    **MOCK_CONFIG,
    CONF_DATA_TYPE: CONF_DATA_TYPE_FORECAST,
}

MOCK_CONFIG_REPORT: Final = {
    **MOCK_CONFIG,
    CONF_DATA_TYPE: CONF_DATA_TYPE_REPORT,
}

MOCK_CONFIG_MIXED: Final = {
    **MOCK_CONFIG,
    CONF_DATA_TYPE: CONF_DATA_TYPE_MIXED,
}

MOCK_CONFIG_HOURLY: Final = {
    **MOCK_CONFIG,
    CONF_HOURLY_UPDATE: True,
}

MOCK_CONFIG_MAP: Final = {
    CONF_ENTITY_TYPE: CONF_ENTITY_TYPE_MAP,
    CONF_LATITUDE: 52.5,
    CONF_LONGITUDE: 13.4,
    CONF_NAME: "DWD Weather Map",
    CONF_MAP_TYPE: CONF_MAP_TYPE_GERMANY,
    CONF_MAP_HOMEMARKER: True,
    CONF_MAP_CENTERMARKER: True,
    CONF_MAP_DARK_MODE: False,
}

# ============================================================================
# Invalid Configuration Test Data
# ============================================================================

MOCK_INVALID_STATION_ID: Final = {
    **MOCK_CONFIG,
    CONF_STATION_ID: "INVALID",
}

MOCK_INVALID_COORDINATES: Final = {
    **MOCK_CONFIG,
    CONF_LATITUDE: 91.0,  # Invalid latitude
    CONF_LONGITUDE: 181.0,  # Invalid longitude
}

# ============================================================================
# Configuration Entry IDs
# ============================================================================

TEST_ENTRY_ID: Final = "test_entry_id_123"
TEST_ENTRY_ID_2: Final = "test_entry_id_456"
