"""Constants for tests."""
from typing import Final
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE, CONF_NAME
from custom_components.dwd_weather.const import DEFAULT_WIND_DIRECTION_TYPE, CONF_WIND_DIRECTION_TYPE, CONF_STATION_ID

from homeassistant.const import CONF_PASSWORD, CONF_USERNAME

# Mock config data to be used across multiple tests
MOCK_CONFIG: Final = {
    CONF_LATITUDE: 0.0,
    CONF_LONGITUDE: 0.0,
    CONF_NAME: "Test Name",
    CONF_WIND_DIRECTION_TYPE: DEFAULT_WIND_DIRECTION_TYPE,
    CONF_STATION_ID: "L732",
}

MOCK_USER_INPUT: Final = {
    CONF_STATION_ID: "L732",
}