"""Support for Deutscher Wetterdienst weather service."""

import logging

from homeassistant.const import (
    DEVICE_CLASS_HUMIDITY,
    DEVICE_CLASS_TEMPERATURE,
    DEVICE_CLASS_PRESSURE,
    LENGTH_KILOMETERS,
    SPEED_METERS_PER_SECOND,
    TEMP_CELSIUS,
    UNIT_PERCENTAGE,
    STATE_UNAVAILABLE,
    STATE_OK,
    ATTR_ATTRIBUTION,
    PRESSURE_HPA,
)
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.typing import ConfigType, HomeAssistantType

from .const import (DOMAIN, DWDWEATHER_DATA, DWDWEATHER_COORDINATOR,
                    DWDWEATHER_NAME, ATTRIBUTION, ATTR_LATEST_UPDATE,
                    ATTR_ISSUE_TIME, ATTR_STATION_ID, ATTR_STATION_NAME)

_LOGGER = logging.getLogger(__name__)

ATTR_LAST_UPDATE = "last_update"
ATTR_SENSOR_ID = "sensor_id"
ATTR_SITE_ID = "site_id"
ATTR_SITE_NAME = "site_name"

# Sensor types are defined as:
#   variable -> [0]title, [1]device_class, [2]units, [3]icon, [4]enabled_by_default
SENSOR_TYPES = {
    "weather": [
        "Weather",
        None,
        None,
        None,
        False,
    ],
    "temperature": [
        "Temperature", DEVICE_CLASS_TEMPERATURE, TEMP_CELSIUS, None, False
    ],
    "dewpoint": [
        "Dewpoint", DEVICE_CLASS_TEMPERATURE, TEMP_CELSIUS, None, False
    ],
    "pressure": [
        "Pressure", DEVICE_CLASS_PRESSURE, PRESSURE_HPA, None, False
    ],
    "wind_speed": [
        "Wind Speed",
        None,
        SPEED_METERS_PER_SECOND,
        "mdi:weather-windy",
        False,
    ],

    # WIND_DIRECTION = "DD" # Unit: Degrees
    # WIND_GUSTS = "FX1" # Unit: m/s
    # PRECIPITATION = "RR1c" # Unit: kg/m2
    # PRECIPITATION_PROBABILITY = "wwP" # Unit: % (0..100)
    # PRECIPITATION_DURATION = "DRR1" # Unit: s
    # CLOUD_COVERAGE = "N" # Unit: % (0..100)
    # VISIBILITY = "VV" # Unit: m
    # SUN_DURATION = "SunD1" # Unit: s
    # SUN_IRRADIANCE = "Rad1h" # Unit: kJ/m2
    # FOG_PROBABILITY = "wwM" # Unit: % (0..100)
    # HUMIDITY
    # "wind_direction": [
    #     "Wind Direction", None, None, "mdi:compass-outline", False
    # ],
    # "wind_gust": [
    #     "Wind Gust", None, SPEED_METERS_PER_SECOND, "mdi:weather-windy", False
    # ],
    # "visibility": ["Visibility", None, None, "mdi:eye", False],
    # "visibility_distance": [
    #     "Visibility Distance",
    #     None,
    #     LENGTH_KILOMETERS,
    #     "mdi:eye",
    #     False,
    # ],
    # "precipitation": [
    #     "Probability of Precipitation",
    #     None,
    #     UNIT_PERCENTAGE,
    #     "mdi:weather-rainy",
    #     False,
    # ],
    # "humidity": [
    #     "Humidity", DEVICE_CLASS_HUMIDITY, UNIT_PERCENTAGE, None, False
    # ],
}


async def async_setup_entry(hass: HomeAssistantType, entry: ConfigType,
                            async_add_entities) -> None:
    """Set up the Met Office weather sensor platform."""
    hass_data = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        [
            DWDWeatherForecastSensor(entry.data, hass_data, sensor_type)
            for sensor_type in SENSOR_TYPES
        ],
        False,
    )


class DWDWeatherForecastSensor(Entity):
    """Implementation of a Met Office current weather condition sensor."""

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

        # WIND_DIRECTION = "DD" # Unit: Degrees
    # WIND_GUSTS = "FX1" # Unit: m/s
    # PRECIPITATION = "RR1c" # Unit: kg/m2
    # PRECIPITATION_PROBABILITY = "wwP" # Unit: % (0..100)
    # PRECIPITATION_DURATION = "DRR1" # Unit: s
    # CLOUD_COVERAGE = "N" # Unit: % (0..100)
    # VISIBILITY = "VV" # Unit: m
    # SUN_DURATION = "SunD1" # Unit: s
    # SUN_IRRADIANCE = "Rad1h" # Unit: kJ/m2
    # FOG_PROBABILITY = "wwM" # Unit: % (0..100)
    # HUMIDITY


        attributes[ATTR_ISSUE_TIME] = self._connector.infos[ATTR_ISSUE_TIME]
        attributes[ATTR_LATEST_UPDATE] = self._connector.infos[
            ATTR_LATEST_UPDATE]
        attributes[ATTR_STATION_ID] = self._connector.infos[ATTR_STATION_ID]
        attributes[ATTR_STATION_NAME] = self._connector.infos[
            ATTR_STATION_NAME]
        attributes[ATTR_ATTRIBUTION] = ATTRIBUTION
        return attributes

    async def async_added_to_hass(self) -> None:
        """Set up a listener and load data."""
        self.async_on_remove(
            self._coordinator.async_add_listener(self.async_write_ha_state))

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
        return self._connector.station_id is not None and self._connector.latest_update is not None
