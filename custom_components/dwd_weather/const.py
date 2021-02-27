"""Constants for the DWD Weather integration."""
from datetime import timedelta

DOMAIN = "dwd_weather"

DEFAULT_NAME = "DWD Weather"
ATTRIBUTION = "Data provided by Deutscher Wetterdienst (DWD)"
ATTR_LATEST_UPDATE = "latest_update_utc"
ATTR_ISSUE_TIME = "forecast_time_utc"
ATTR_STATION_ID = "station_id"
ATTR_STATION_NAME = "station_name"

DEFAULT_SCAN_INTERVAL = timedelta(minutes=15)

DWDWEATHER_DATA = "dwd_weather_data"
DWDWEATHER_COORDINATOR = "dwd_weather_coordinator"
DWDWEATHER_MONITORED_CONDITIONS = "dwd_weather_monitored_conditions"
DWDWEATHER_NAME = "dwd_weather_name"

CONF_STATION_ID = "station_id"
CONF_WEATHER_INTERVAL = "weather_interval"
