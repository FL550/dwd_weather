"""Sensor for Deutscher Wetterdienst weather service."""

import logging

from homeassistant.const import (
    ATTR_ATTRIBUTION,
    DEGREE,
    DEVICE_CLASS_HUMIDITY,
    DEVICE_CLASS_PRESSURE,
    DEVICE_CLASS_TEMPERATURE,
    LENGTH_KILOMETERS,
    PRESSURE_HPA,
    SPEED_METERS_PER_SECOND,
    STATE_OK,
    STATE_UNAVAILABLE,
    TEMP_CELSIUS,
    TIME_SECONDS,
    UNIT_PERCENTAGE,
)
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.typing import ConfigType, HomeAssistantType

from .const import (
    ATTR_ISSUE_TIME,
    ATTR_LATEST_UPDATE,
    ATTR_STATION_ID,
    ATTR_STATION_NAME,
    ATTRIBUTION,
    DOMAIN,
    DWDWEATHER_COORDINATOR,
    DWDWEATHER_DATA,
    DWDWEATHER_NAME,
)

_LOGGER = logging.getLogger(__name__)

ATTR_LAST_UPDATE = "last_update"
ATTR_SENSOR_ID = "sensor_id"
ATTR_SITE_ID = "site_id"
ATTR_SITE_NAME = "site_name"

# Sensor types are defined as:
#   variable -> [0]title, [1]device_class, [2]units, [3]icon, [4]enabled_by_default
SENSOR_TYPES = {
    "weather": ["Weather", None, None, "mdi:weather-partly-cloudy", False],
    "temperature": [
        "Temperature",
        DEVICE_CLASS_TEMPERATURE,
        TEMP_CELSIUS,
        "mdi:temperature-celsius",
        False,
    ],
    "dewpoint": [
        "Dewpoint",
        DEVICE_CLASS_TEMPERATURE,
        TEMP_CELSIUS,
        "mdi:temperature-celsius",
        False,
    ],
    "pressure": ["Pressure", DEVICE_CLASS_PRESSURE, PRESSURE_HPA, None, False],
    "wind_speed": [
        "Wind Speed",
        None,
        SPEED_METERS_PER_SECOND,
        "mdi:weather-windy",
        False,
    ],
    "wind_direction": ["Wind Direction", None, DEGREE, "mdi:compass-outline", False],
    "wind_gusts": [
        "Wind Gusts",
        None,
        SPEED_METERS_PER_SECOND,
        "mdi:weather-windy",
        False,
    ],
    "precipitation": ["Precipitation", None, "kg/m^2", "mdi:weather-rainy", False],
    "precipitation_probability": [
        "Precipitation Probability",
        None,
        UNIT_PERCENTAGE,
        "mdi:weather-rainy",
        False,
    ],
    "precipitation_duration": [
        "Precipitation Duration",
        None,
        TIME_SECONDS,
        "mdi:weather-rainy",
        False,
    ],
    "cloud_coverage": ["Cloud Coverage", None, UNIT_PERCENTAGE, "mdi:cloud", False],
    "visibility": ["Visibility", None, LENGTH_KILOMETERS, "mdi:eye", False],
    "sun_duration": ["Sun Duration", None, TIME_SECONDS, "mdi:weather-sunset", False],
    "sun_irradiance": [
        "Sun Irradiance",
        None,
        "kJ/m^2",
        "mdi:weather-sunny-alert",
        False,
    ],
    "fog_probability": [
        "Fog Probability",
        None,
        UNIT_PERCENTAGE,
        "mdi:weather-fog",
        False,
    ],
    "humidity": [
        "Humidity",
        DEVICE_CLASS_HUMIDITY,
        UNIT_PERCENTAGE,
        "mdi:water-percent",
        False,
    ],
}


async def async_setup_entry(
    hass: HomeAssistantType, entry: ConfigType, async_add_entities
) -> None:
    """Set up the DWD weather sensor platform."""
    hass_data = hass.data[DOMAIN][entry.entry_id]
    _LOGGER.debug("Sensor async_setup_entry")
    async_add_entities(
        [
            DWDWeatherForecastSensor(entry.data, hass_data, sensor_type)
            for sensor_type in SENSOR_TYPES
        ],
        False,
    )


class DWDWeatherForecastSensor(Entity):
    """Implementation of a DWD current weather condition sensor."""

    def __init__(self, entry_data, hass_data, sensor_type):
        """Initialize the sensor."""
        self._connector = hass_data[DWDWEATHER_DATA]
        self._coordinator = hass_data[DWDWEATHER_COORDINATOR]

        self._type = sensor_type
        self._name = f"{SENSOR_TYPES[self._type][0]} {hass_data[DWDWEATHER_NAME]}"
        self._unique_id = f"{SENSOR_TYPES[self._type][0]}_{self._connector.dwd_weather.get_station_name(False).lower()}"

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def unique_id(self):
        """Return the unique of the sensor."""
        return self._unique_id

    @property
    def state(self):
        """Return the state of the sensor."""
        if self._connector.latest_update:
            return STATE_OK
        return STATE_UNAVAILABLE

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
    def device_state_attributes(self):
        """Return the state attributes of the device."""
        attributes = {}

        if self._type == "weather":
            attributes["data"] = self._connector.get_condition_hourly()
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

    async def async_added_to_hass(self) -> None:
        """Set up a listener and load data."""
        self.async_on_remove(
            self._coordinator.async_add_listener(self.async_write_ha_state)
        )

    async def async_update(self):
        """Schedule a custom update via the common entity update service."""
        await self._coordinator.async_request_refresh()

    @property
    def should_poll(self) -> bool:
        """Entities do not individually poll."""
        return False

    @property
    def entity_registry_enabled_default(self) -> bool:
        """Return if the entity should be enabled when first added to the entity registry."""
        return SENSOR_TYPES[self._type][4]

    @property
    def available(self):
        """Return if state is available."""
        return (
            self._connector.station_id is not None
            and self._connector.latest_update is not None
        )
