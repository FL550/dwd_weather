"""Sensor for Deutscher Wetterdienst weather service."""

import logging
import re
from custom_components.dwd_weather.connector import DWDWeatherData
from custom_components.dwd_weather.entity import DWDWeatherEntity
from homeassistant.components.sensor.const import SensorStateClass

from homeassistant.const import (
    ATTR_ATTRIBUTION,
    DEGREE,
    PERCENTAGE,
    UnitOfIrradiance,
    UnitOfLength,
    UnitOfPressure,
    UnitOfSpeed,
    UnitOfTemperature,
    UnitOfTime,
    UnitOfVolumetricFlux,
)
from homeassistant.components.sensor import (
    SensorEntity,
)

from homeassistant.components.sensor.const import (
    SensorDeviceClass,
)

from homeassistant.core import HomeAssistant

from homeassistant.helpers.typing import ConfigType

from .const import (
    ATTR_REPORT_ISSUE_TIME,
    ATTR_ISSUE_TIME,
    ATTR_LATEST_UPDATE,
    ATTR_STATION_ID,
    ATTR_STATION_NAME,
    ATTRIBUTION,
    CONF_DATA_TYPE,
    CONF_DATA_TYPE_FORECAST,
    CONF_HOURLY_UPDATE,
    CONF_STATION_ID,
    CONF_STATION_NAME,
    DOMAIN,
    DWDWEATHER_COORDINATOR,
    DWDWEATHER_DATA,
)

_LOGGER = logging.getLogger(__name__)

ATTR_LAST_UPDATE = "last_update"
ATTR_SENSOR_ID = "sensor_id"
ATTR_SITE_ID = "site_id"
ATTR_SITE_NAME = "site_name"

# Sensor types are defined as:
#   variable -> [0]title, [1]device_class, [2]units, [3]icon, [4]enabled_by_default, [5]state_class, [6]enabled_in_hourly_update
SENSOR_TYPES = {
    "weather_condition": [
        "Weather",
        None,
        None,
        "mdi:weather-partly-cloudy",
        False,
        SensorStateClass.MEASUREMENT,
        True,
    ],
    "weather_report": [
        "Weather Report",
        None,
        None,
        "mdi:weather-partly-cloudy",
        False,
        None,
        True,
    ],
    "temperature": [
        "Temperature",
        SensorDeviceClass.TEMPERATURE,
        UnitOfTemperature.CELSIUS,
        "mdi:temperature-celsius",
        False,
        SensorStateClass.MEASUREMENT,
        True,
    ],
    "dewpoint": [
        "Dewpoint",
        SensorDeviceClass.TEMPERATURE,
        UnitOfTemperature.CELSIUS,
        "mdi:temperature-celsius",
        False,
        SensorStateClass.MEASUREMENT,
        True,
    ],
    "pressure": [
        "Pressure",
        SensorDeviceClass.PRESSURE,
        UnitOfPressure.HPA,
        None,
        False,
        SensorStateClass.MEASUREMENT,
        True,
    ],
    "wind_speed": [
        "Wind Speed",
        None,
        UnitOfSpeed.KILOMETERS_PER_HOUR,
        "mdi:weather-windy",
        False,
        SensorStateClass.MEASUREMENT,
        True,
    ],
    "wind_direction": [
        "Wind Direction",
        None,
        DEGREE,
        "mdi:compass-outline",
        False,
        SensorStateClass.MEASUREMENT,
        True,
    ],
    "wind_gusts": [
        "Wind Gusts",
        None,
        UnitOfSpeed.KILOMETERS_PER_HOUR,
        "mdi:weather-windy",
        False,
        SensorStateClass.MEASUREMENT,
        True,
    ],
    "precipitation": [
        "Precipitation",
        None,
        UnitOfVolumetricFlux.MILLIMETERS_PER_HOUR,
        "mdi:weather-rainy",
        False,
        SensorStateClass.MEASUREMENT,
        True,
    ],
    "precipitation_probability": [
        "Precipitation Probability",
        None,
        PERCENTAGE,
        "mdi:weather-rainy",
        False,
        SensorStateClass.MEASUREMENT,
        False,
    ],
    "precipitation_duration": [
        "Precipitation Duration",
        None,
        UnitOfTime.SECONDS,
        "mdi:weather-rainy",
        False,
        SensorStateClass.MEASUREMENT,
        False,
    ],
    "cloud_coverage": [
        "Cloud Coverage",
        None,
        PERCENTAGE,
        "mdi:cloud",
        False,
        SensorStateClass.MEASUREMENT,
        True,
    ],
    "visibility": [
        "Visibility",
        None,
        UnitOfLength.KILOMETERS,
        "mdi:eye",
        False,
        SensorStateClass.MEASUREMENT,
        True,
    ],
    "sun_duration": [
        "Sun Duration",
        None,
        UnitOfTime.SECONDS,
        "mdi:weather-sunset",
        False,
        SensorStateClass.MEASUREMENT,
        True,
    ],
    "sun_irradiance": [
        "Sun Irradiance",
        None,
        UnitOfIrradiance.WATTS_PER_SQUARE_METER,
        "mdi:weather-sunny-alert",
        False,
        SensorStateClass.MEASUREMENT,
        True,
    ],
    "fog_probability": [
        "Fog Probability",
        None,
        PERCENTAGE,
        "mdi:weather-fog",
        False,
        SensorStateClass.MEASUREMENT,
        True,
    ],
    "humidity": [
        "Humidity",
        SensorDeviceClass.HUMIDITY,
        PERCENTAGE,
        "mdi:water-percent",
        False,
        SensorStateClass.MEASUREMENT,
        True,
    ],
    "humidity_absolute": [
        "Absolute Humidity",
        None,
        "g/m³",
        "mdi:water",
        False,
        SensorStateClass.MEASUREMENT,
        True,
    ],
    "measured_values_time": [
        "Report Time (UTC)",
        "",
        "",
        "mdi:clock-time-four-outline",
        True,
        None,
        True,
    ],
    "forecast_values_time": [
        "Forecast Time (UTC)",
        "",
        "",
        "mdi:clock-time-four-outline",
        True,
        None,
        True,
    ],
    "uv_index": [
        "UV-Index",
        "",
        "",
        "mdi:sun-wireless",
        False,
        None,
        True,
    ],
    "evaporation": [
        "Evaporation",
        "",
        "kg/m²",
        "mdi:waves-arrow-up",
        False,
        None,
        False,
    ],
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigType, async_add_entities
) -> None:
    """Set up the DWD weather sensor platform."""
    hass_data = hass.data[DOMAIN][entry.entry_id]  # type: ignore
    _LOGGER.debug("Sensor async_setup_entry {}".format(entry.data))  # type: ignore
    if CONF_STATION_ID in entry.data:  # type: ignore
        _LOGGER.debug("Sensor async_setup_entry")
        # Only add the report sensor if a report is available
        sensor_list = {
            k: v
            for k, v in SENSOR_TYPES.items()
            if k != "measured_values_time"
            # and contains_weather_data(k, hass_data[DWDWEATHER_DATA])
            and not (
                hass_data[DWDWEATHER_DATA]._config[CONF_HOURLY_UPDATE] and not v[6]
            )
        }
        async_add_entities(
            [
                DWDWeatherForecastSensor(entry.data, hass_data, sensor_type)  # type: ignore
                for sensor_type in sensor_list
            ],
            False,
        )
        if (
            hass_data[DWDWEATHER_DATA]._config[CONF_DATA_TYPE]
            != CONF_DATA_TYPE_FORECAST
        ):
            async_add_entities(
                [
                    DWDWeatherForecastSensor(
                        entry.data,  # type: ignore
                        hass_data,
                        "measured_values_time",  # type: ignore
                    )
                ],
                False,
            )


class DWDWeatherForecastSensor(DWDWeatherEntity, SensorEntity):
    """Implementation of a DWD current weather condition sensor."""

    def __init__(self, entry_data, hass_data, sensor_type):
        """Initialize the sensor."""
        dwd_data: DWDWeatherData = hass_data[DWDWEATHER_DATA]
        self._coordinator = hass_data[DWDWEATHER_COORDINATOR]
        self._type = sensor_type

        # name = f"{dwd_data._config[CONF_STATION_NAME]}: {SENSOR_TYPES[self._type][0]}"
        unique_id = f"{dwd_data._config[CONF_STATION_ID]}_{dwd_data._config[CONF_STATION_NAME]}_{SENSOR_TYPES[self._type][0]}"
        _LOGGER.debug(
            "Setting up sensor with id {} and name {}".format(
                unique_id, SENSOR_TYPES[self._type][0]
            )
        )
        super().__init__(hass_data, unique_id)

    @property
    def translation_key(self):
        """Return the current condition."""
        return self._type

    @property
    def state(self):
        """Return the state of the sensor."""
        result = ""
        if self._type == "weather_condition":
            result = self._connector.get_condition()
        elif self._type == "weather_report":
            result = (
                re.search(
                    r"\w+, \d{2}\.\d{2}\.\d{2}, \d{2}:\d{2}",
                    self._connector.get_weather_report(),
                ).group()  # type: ignore
                if self._connector.get_weather_report() is not None
                else None
            )
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
        elif self._type == "humidity_absolute":
            result = self._connector.get_humidity_absolute()
        elif self._type == "measured_values_time":
            result = self._connector.infos[ATTR_REPORT_ISSUE_TIME]
        elif self._type == "forecast_values_time":
            result = self._connector.infos[ATTR_ISSUE_TIME]
        elif self._type == "uv_index":
            result = self._connector.get_uv_index()
        elif self._type == "evaporation":
            result = self._connector.get_evaporation()
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
        elif self._type == "humidity_absolute":
            attributes["data"] = self._connector.get_humidity_absolute_hourly()
        elif self._type == "uv_index":
            attributes["data"] = self._connector.get_uv_index_daily()
        elif self._type == "evaporation":
            attributes["data"] = self._connector.get_evaporation_daily()

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

    async def async_added_to_hass(self) -> None:
        """Connect to dispatcher listening for entity data notifications."""
        self.async_on_remove(
            self._coordinator.async_add_listener(self.async_write_ha_state)
        )

    async def async_update(self) -> None:
        """Get the latest data and updates the states."""
        await self._coordinator.async_request_refresh()
