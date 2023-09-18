"""Sensor for Deutscher Wetterdienst weather service."""

import logging
import re
from custom_components.dwd_weather.connector import DWDWeatherData
from custom_components.dwd_weather.entity import DWDWeatherEntity

from homeassistant.const import (
    ATTR_ATTRIBUTION,
    DEGREE,
    DEVICE_CLASS_HUMIDITY,
    DEVICE_CLASS_PRESSURE,
    DEVICE_CLASS_TEMPERATURE,
    LENGTH_KILOMETERS,
    PRESSURE_HPA,
    SPEED_KILOMETERS_PER_HOUR,
    TEMP_CELSIUS,
    TIME_SECONDS,
)
from homeassistant.components.sensor import (
    STATE_CLASS_MEASUREMENT,
    SensorEntity,
)

from homeassistant.helpers.typing import ConfigType, HomeAssistantType

from .const import (
    ATTR_ISSUE_TIME,
    ATTR_LATEST_UPDATE,
    ATTR_STATION_ID,
    ATTR_STATION_NAME,
    ATTRIBUTION,
    CONF_STATION_ID,
    CONF_STATION_NAME,
    DOMAIN,
    DWDWEATHER_DATA,
)

_LOGGER = logging.getLogger(__name__)

ATTR_LAST_UPDATE = "last_update"
ATTR_SENSOR_ID = "sensor_id"
ATTR_SITE_ID = "site_id"
ATTR_SITE_NAME = "site_name"

# Sensor types are defined as:
#   variable -> [0]title, [1]device_class, [2]units, [3]icon, [4]enabled_by_default [5]state_class
SENSOR_TYPES = {
    "weather": [
        "Weather",
        None,
        None,
        "mdi:weather-partly-cloudy",
        False,
        STATE_CLASS_MEASUREMENT,
    ],
    "weather_report": [
        "Weather Report",
        None,
        None,
        "mdi:weather-partly-cloudy",
        False,
        None,
    ],
    "temperature": [
        "Temperature",
        DEVICE_CLASS_TEMPERATURE,
        TEMP_CELSIUS,
        "mdi:temperature-celsius",
        False,
        STATE_CLASS_MEASUREMENT,
    ],
    "dewpoint": [
        "Dewpoint",
        DEVICE_CLASS_TEMPERATURE,
        TEMP_CELSIUS,
        "mdi:temperature-celsius",
        False,
        STATE_CLASS_MEASUREMENT,
    ],
    "pressure": [
        "Pressure",
        DEVICE_CLASS_PRESSURE,
        PRESSURE_HPA,
        None,
        False,
        STATE_CLASS_MEASUREMENT,
    ],
    "wind_speed": [
        "Wind Speed",
        None,
        SPEED_KILOMETERS_PER_HOUR,
        "mdi:weather-windy",
        False,
        STATE_CLASS_MEASUREMENT,
    ],
    "wind_direction": [
        "Wind Direction",
        None,
        DEGREE,
        "mdi:compass-outline",
        False,
        STATE_CLASS_MEASUREMENT,
    ],
    "wind_gusts": [
        "Wind Gusts",
        None,
        SPEED_KILOMETERS_PER_HOUR,
        "mdi:weather-windy",
        False,
        STATE_CLASS_MEASUREMENT,
    ],
    "precipitation": [
        "Precipitation",
        None,
        "mm/m^2",
        "mdi:weather-rainy",
        False,
        STATE_CLASS_MEASUREMENT,
    ],
    "precipitation_probability": [
        "Precipitation Probability",
        None,
        "%",
        "mdi:weather-rainy",
        False,
        STATE_CLASS_MEASUREMENT,
    ],
    "precipitation_duration": [
        "Precipitation Duration",
        None,
        TIME_SECONDS,
        "mdi:weather-rainy",
        False,
        STATE_CLASS_MEASUREMENT,
    ],
    "cloud_coverage": [
        "Cloud Coverage",
        None,
        "%",
        "mdi:cloud",
        False,
        STATE_CLASS_MEASUREMENT,
    ],
    "visibility": [
        "Visibility",
        None,
        LENGTH_KILOMETERS,
        "mdi:eye",
        False,
        STATE_CLASS_MEASUREMENT,
    ],
    "sun_duration": [
        "Sun Duration",
        None,
        TIME_SECONDS,
        "mdi:weather-sunset",
        False,
        STATE_CLASS_MEASUREMENT,
    ],
    "sun_irradiance": [
        "Sun Irradiance",
        None,
        "W/m^2",
        "mdi:weather-sunny-alert",
        False,
        STATE_CLASS_MEASUREMENT,
    ],
    "fog_probability": [
        "Fog Probability",
        None,
        "%",
        "mdi:weather-fog",
        False,
        STATE_CLASS_MEASUREMENT,
    ],
    "humidity": [
        "Humidity",
        DEVICE_CLASS_HUMIDITY,
        "%",
        "mdi:water-percent",
        False,
        STATE_CLASS_MEASUREMENT,
    ],
}


async def async_setup_entry(
    hass: HomeAssistantType, entry: ConfigType, async_add_entities
) -> None:
    """Set up the DWD weather sensor platform."""
    hass_data = hass.data[DOMAIN][entry.entry_id]
    _LOGGER.debug("Sensor async_setup_entry {}".format(entry.data))
    if CONF_STATION_ID in entry.data:
        _LOGGER.debug("Sensor async_setup_entry")
        async_add_entities(
            [
                DWDWeatherForecastSensor(entry.data, hass_data, sensor_type)
                for sensor_type in SENSOR_TYPES
            ],
            False,
        )


class DWDWeatherForecastSensor(DWDWeatherEntity, SensorEntity):
    """Implementation of a DWD current weather condition sensor."""

    def __init__(self, entry_data, hass_data, sensor_type):
        """Initialize the sensor."""
        dwd_data: DWDWeatherData = hass_data[DWDWEATHER_DATA]
        self._type = sensor_type

        name = f"{dwd_data._config[CONF_STATION_NAME]}: {SENSOR_TYPES[self._type][0]}"
        unique_id = f"{dwd_data._config[CONF_STATION_ID]}_{SENSOR_TYPES[self._type][0]}"
        _LOGGER.debug(
            "Setting up sensor with id {} and name {}".format(unique_id, name)
        )
        super().__init__(hass_data, unique_id, name)

    @property
    def translation_key(self):
        """Return the current condition."""
        return "dwd_weather_condition"

    @property
    def state(self):
        """Return the state of the sensor."""
        result = ""
        if self._type == "weather":
            result = self._connector.get_condition()
        elif self._type == "weather_report":
            result = re.search(
                "\w+, \d{2}\.\d{2}\.\d{2}, \d{2}:\d{2}",
                self._connector.get_weather_report(),
            ).group()
        elif self._type == "temperature":
            result = self._connector.get_temperature()
        elif self._type == "dewpoint":
            result = self._connector.get_dewpoint()
        elif self._type == "pressure":
            result = self._connector.get_pressure()
        elif self._type == "wind_speed":
            result = self._connector.get_wind_speed()
        elif self._type == "wind_direction":
            result = self._connector.get_wind_direction()
        elif self._type == "wind_gusts":
            result = self._connector.get_wind_gusts()
        elif self._type == "precipitation":
            result = self._connector.get_precipitation()
        elif self._type == "precipitation_probability":
            result = self._connector.get_precipitation_probability()
        elif self._type == "precipitation_duration":
            result = self._connector.get_precipitation_duration()
        elif self._type == "cloud_coverage":
            result = self._connector.get_cloud_coverage()
        elif self._type == "visibility":
            result = self._connector.get_visibility()
        elif self._type == "sun_duration":
            result = self._connector.get_sun_duration()
        elif self._type == "sun_irradiance":
            result = self._connector.get_sun_irradiance()
        elif self._type == "fog_probability":
            result = self._connector.get_fog_probability()
        elif self._type == "humidity":
            result = self._connector.get_humidity()
        return result

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return SENSOR_TYPES[self._type][2]

    @property
    def icon(self):
        """Return the icon for the entity card."""
        value = SENSOR_TYPES[self._type][3]
        if self._type == "weather":
            value = self.state
            if value is None:
                value = "sunny"
            elif value == "partlycloudy":
                value = "partly-cloudy"
            value = f"mdi:weather-{value}"

        return value

    @property
    def device_class(self):
        """Return the device class of the sensor."""
        return SENSOR_TYPES[self._type][1]

    @property
    def state_class(self):
        """Return the state class of the sensor."""
        return SENSOR_TYPES[self._type][5]

    @property
    def extra_state_attributes(self):
        """Return the state attributes of the device."""
        attributes = {}

        if self._type == "weather":
            attributes["data"] = self._connector.get_condition_hourly()
        elif self._type == "weather_report":
            attributes["data"] = self._connector.get_weather_report()
        elif self._type == "temperature":
            attributes["data"] = self._connector.get_temperature_hourly()
        elif self._type == "dewpoint":
            attributes["data"] = self._connector.get_dewpoint_hourly()
        elif self._type == "pressure":
            attributes["data"] = self._connector.get_pressure_hourly()
        elif self._type == "wind_speed":
            attributes["data"] = self._connector.get_wind_speed_hourly()
        elif self._type == "wind_direction":
            attributes["data"] = self._connector.get_wind_direction_hourly()
        elif self._type == "wind_gusts":
            attributes["data"] = self._connector.get_wind_gusts_hourly()
        elif self._type == "precipitation":
            attributes["data"] = self._connector.get_precipitation_hourly()
        elif self._type == "precipitation_probability":
            attributes["data"] = self._connector.get_precipitation_probability_hourly()
        elif self._type == "precipitation_duration":
            attributes["data"] = self._connector.get_precipitation_duration_hourly()
        elif self._type == "cloud_coverage":
            attributes["data"] = self._connector.get_cloud_coverage_hourly()
        elif self._type == "visibility":
            attributes["data"] = self._connector.get_visibility_hourly()
        elif self._type == "sun_duration":
            attributes["data"] = self._connector.get_sun_duration_hourly()
        elif self._type == "sun_irradiance":
            attributes["data"] = self._connector.get_sun_irradiance_hourly()
        elif self._type == "fog_probability":
            attributes["data"] = self._connector.get_fog_probability_hourly()
        elif self._type == "humidity":
            attributes["data"] = self._connector.get_humidity_hourly()

        attributes[ATTR_ISSUE_TIME] = self._connector.infos[ATTR_ISSUE_TIME]
        attributes[ATTR_LATEST_UPDATE] = self._connector.infos[ATTR_LATEST_UPDATE]
        attributes[ATTR_STATION_ID] = self._connector.infos[ATTR_STATION_ID]
        attributes[ATTR_STATION_NAME] = self._connector.infos[ATTR_STATION_NAME]
        attributes[ATTR_ATTRIBUTION] = ATTRIBUTION
        return attributes

    @property
    def entity_registry_enabled_default(self) -> bool:
        """Return if the entity should be enabled when first added to the entity registry."""
        return SENSOR_TYPES[self._type][4]

    @property
    def available(self):
        """Return if state is available."""
        return self._connector.latest_update is not None
