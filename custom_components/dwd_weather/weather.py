"""Support for DWD weather service."""
import logging
from datetime import datetime, timezone

from homeassistant.components.weather import WeatherEntity
from homeassistant.const import (
    TEMP_CELSIUS,)

from homeassistant.helpers.typing import ConfigType, HomeAssistantType

from .const import (DEFAULT_NAME, ATTRIBUTION, DOMAIN, DWDWEATHER_DATA,
                    DWDWEATHER_COORDINATOR, DWDWEATHER_NAME)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistantType, entry: ConfigType,
                            async_add_entities) -> None:
    """Add a weather entity from a config_entry."""
    hass_data = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([DWDWeather(entry.data, hass_data)], False)


class DWDWeather(WeatherEntity):
    """Implementation of DWD weather."""

    def __init__(self, entry_data, hass_data):
        """Initialise the platform with a data instance and site."""
        self._connector = hass_data[DWDWEATHER_DATA]
        self._coordinator = hass_data[DWDWEATHER_COORDINATOR]

        self._name = f"{DEFAULT_NAME} {hass_data[DWDWEATHER_NAME]}"
        self._unique_id = f"{self._connector.weather_data.get_station_name(False).lower()}"

    async def async_added_to_hass(self):
        """When entity is added to hass."""
        self.async_on_remove(
            self._coordinator.async_add_listener(self.async_write_ha_state))

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def unique_id(self):
        """Return unique ID."""
        return self._unique_id

    @property
    def name(self):
        """Return the name of the sensor."""
        self._name

    @property
    def condition(self):
        """Return the current condition."""
        return self._connector.weather_data.get_forecast_condition(
            datetime.now(timezone.utc), False)

    @property
    def temperature(self):
        """Return the temperature."""
        return round(
            float(
                self._connector.weather_data.get_forecast_temperature(
                    datetime.now(timezone.utc), False)), 1)

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return TEMP_CELSIUS

    @property
    def pressure(self):
        """Return the pressure."""
        return round(
            float(
                self._connector.weather_data.get_forecast_pressure(
                    datetime.now(timezone.utc), False)), 1)

    @property
    def wind_speed(self):
        """Return the wind speed."""
        return round(
            float(
                self._connector.weather_data.get_forecast_wind_speed(
                    datetime.now(timezone.utc), False)), 1)

    @property
    def wind_bearing(self):
        """Return the wind direction."""
        return round(
            float(
                self._connector.weather_data.get_forecast_wind_direction(
                    datetime.now(timezone.utc), False)), 1)

    @property
    def visibility(self):
        """Return the visibility."""
        return round(
            float(
                self._connector.weather_data.get_forecast_visibility(
                    datetime.now(timezone.utc), False)) / 1000, 1)

    @property
    def humidity(self):
        """Return the relative humidity."""
        return None

    @property
    def attribution(self):
        """Return the attribution."""
        return ATTRIBUTION

    @property
    def forecast(self):
        """Return the forecast array."""
        return self._connector.forecast

    @property
    def device_state_attributes(self):
        """Return data validity infos."""
        return self._connector.infos
