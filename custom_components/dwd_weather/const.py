"""Constants for the DWD Weather integration."""
from datetime import timedelta
from typing import Final

from homeassistant.const import Platform

DOMAIN: Final = "dwd_weather"
# Platforms
PLATFORMS: Final = [
    Platform.SENSOR,
    Platform.WEATHER,
]
INTEGRATION_VERSION: Final = "1.2.28"
MIN_REQUIRED_HA_VERSION: Final = "2022.7.1"

DEFAULT_NAME: Final = "DWD Weather"
ATTRIBUTION: Final = "Data provided by Deutscher Wetterdienst (DWD)"
ATTR_LATEST_UPDATE = "latest_update_utc"
ATTR_ISSUE_TIME = "forecast_time_utc"
ATTR_STATION_ID = "station_id"
ATTR_STATION_NAME = "station_name"

DEFAULT_SCAN_INTERVAL = timedelta(minutes=1)
DEFAULT_WIND_DIRECTION_TYPE = "DEGREES"

DWDWEATHER_DATA = "dwd_weather_data"
DWDWEATHER_COORDINATOR = "dwd_weather_coordinator"
DWDWEATHER_MONITORED_CONDITIONS = "dwd_weather_monitored_conditions"
DWDWEATHER_NAME = "dwd_weather_name"

CONF_STATION_ID = "station_id"
CONF_WEATHER_INTERVAL = "weather_interval"
CONF_WIND_DIRECTION_TYPE = "wind_direction_type"
