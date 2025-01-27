"""Constants for the DWD Weather integration."""

from datetime import timedelta

from homeassistant.const import Platform

# Base component constants
NAME = "DWD Weather"
DOMAIN = "dwd_weather"
CONF_VERSION = 10
ATTRIBUTION = "Data provided by Deutscher Wetterdienst (DWD)"
# Platforms
PLATFORMS = [
    Platform.SENSOR,
    Platform.WEATHER,
]
INTEGRATION_VERSION = "0.0.0.dev0"
MIN_REQUIRED_HA_VERSION = "2024.10"

ATTR_LATEST_UPDATE = "latest_update_utc"
ATTR_REPORT_ISSUE_TIME = "report_time_utc"
ATTR_ISSUE_TIME = "forecast_time_utc"
ATTR_STATION_ID = "station_id"
ATTR_STATION_NAME = "station_name"

ATTR_FORECAST_SUN_DURATION = "sun_duration"
ATTR_FORECAST_PRESSURE = "pressure"
ATTR_FORECAST_PRECIPITATION_DURATION = "precipitation_duration"
ATTR_FORECAST_CLOUD_COVERAGE = "cloud_coverage"
ATTR_FORECAST_VISIBILITY = "visibility"
ATTR_FORECAST_SUN_IRRADIANCE = "sun_irradiance"
ATTR_FORECAST_FOG_PROBABILITY = "fog_probability"
ATTR_FORECAST_EVAPORATION = "evaporation"

DEFAULT_SCAN_INTERVAL = timedelta(minutes=1)
DEFAULT_MAP_INTERVAL = timedelta(minutes=1)
DEFAULT_WIND_DIRECTION_TYPE = "degrees"
DEFAULT_INTERPOLATION = True

DWDWEATHER_DATA = "dwd_weather_data"
DWDWEATHER_COORDINATOR = "dwd_weather_coordinator"
DWDWEATHER_MONITORED_CONDITIONS = "dwd_weather_monitored_conditions"

CONF_ENTITY_TYPE = "entity_type"
CONF_ENTITY_TYPE_STATION = "weather_station"
CONF_ENTITY_TYPE_MAP = "weather_map"
CONF_STATION_ID = "station_id"
CONF_MAP_ID = "map_id"
CONF_CUSTOM_LOCATION = "custom_location"
CONF_LOCATION_COORDINATES = "location_type"
CONF_DATA_TYPE = "data_type"
CONF_DATA_TYPE_MIXED = "mixed_data"
CONF_DATA_TYPE_REPORT = "report_data"
CONF_DATA_TYPE_FORECAST = "forecast_data"
CONF_STATION_NAME = "station_name"
CONF_WIND_DIRECTION_TYPE = "wind_direction_type"
CONF_INTERPOLATE = "interpolate"
CONF_HOURLY_UPDATE = "hourly_update"
CONF_ADDITIONAL_FORECAST_ATTRIBUTES = "additional_forecast_attributes"

CONF_MAP_TYPE = "map_type"
CONF_MAP_TYPE_GERMANY = "map_germany"
CONF_MAP_TYPE_CUSTOM = "map_custom"
CONF_MAP_WINDOW = "map_window"
CONF_MAP_DARK_MODE = "map_dark_mode"
CONF_MAP_FOREGROUND_TYPE = "map_foreground_type"
CONF_MAP_FOREGROUND_PRECIPITATION = "map_foreground_precipitation"
CONF_MAP_FOREGROUND_MAXTEMP = "map_foreground_maxtemp"
CONF_MAP_FOREGROUND_UVINDEX = "map_foreground_uvindex"
CONF_MAP_FOREGROUND_POLLENFLUG = "map_foreground_pollenflug"
CONF_MAP_FOREGROUND_SATELLITE_RGB = "map_foreground_satellite_rgb"
CONF_MAP_FOREGROUND_SATELLITE_IR = "map_foreground_satellite_ir"
CONF_MAP_FOREGROUND_WARNUNGEN_GEMEINDEN = "map_foreground_warnungen_gem"
CONF_MAP_FOREGROUND_WARNUNGEN_KREISE = "map_foreground_warnungen_kreise"
CONF_MAP_BACKGROUND_TYPE = "map_background_type"
CONF_MAP_BACKGROUND_LAENDER = "map_background_laender"
CONF_MAP_BACKGROUND_BUNDESLAENDER = "map_background_bundeslaender"
CONF_MAP_BACKGROUND_KREISE = "map_background_kreise"
CONF_MAP_BACKGROUND_GEMEINDEN = "map_background_gemeinden"
CONF_MAP_BACKGROUND_SATELLIT = "map_background_satellit"
CONF_MAP_CENTERMARKER = "map_marker"
CONF_MAP_HOMEMARKER = "map_homemarker"
CONF_MAP_HOMEMARKER_SHAPE = "map_homemarker_shape"
CONF_MAP_HOMEMARKER_SIZE = "map_homemarker_size"
CONF_MAP_HOMEMARKER_COLOR = "map_homemarker_color"
CONF_MAP_TIMESTAMP = "map_timestamp"
CONF_MAP_LOOP_COUNT = "map_loop_count"
CONF_MAP_LOOP_SPEED = "map_loop_speed"

conversion_table_map_foreground = {
    CONF_MAP_FOREGROUND_PRECIPITATION: "Precipitation",
    CONF_MAP_FOREGROUND_MAXTEMP: "Temperature",
    CONF_MAP_FOREGROUND_UVINDEX: "UV-Index",
    CONF_MAP_FOREGROUND_POLLENFLUG: "Pollen",
    CONF_MAP_FOREGROUND_SATELLITE_RGB: "Satellite RGB",
    CONF_MAP_FOREGROUND_SATELLITE_IR: "Satellite IR",
    CONF_MAP_FOREGROUND_WARNUNGEN_GEMEINDEN: "Warnungen Gemeinden",
    CONF_MAP_FOREGROUND_WARNUNGEN_KREISE: "Warnungen Kreise",
}

CONF_MAP_HOMEMARKER_SHAPE_CIRCLE = "map_homemarker_shape_circle"
CONF_MAP_HOMEMARKER_SHAPE_CROSS = "map_homemarker_shape_cross"
CONF_MAP_HOMEMARKER_SHAPE_SQUARE = "map_homemarker_shape_square"

CONF_OPTION_MAP_MESSAGE = "map_options_message"
