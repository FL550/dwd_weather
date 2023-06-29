"""Support for DWD weather service."""
import logging
from custom_components.dwd_weather.connector import DWDWeatherData
from custom_components.dwd_weather.entity import DWDWeatherEntity

from homeassistant.components.weather import WeatherEntity
from homeassistant.const import (
    TEMP_CELSIUS,
    PRESSURE_HPA,
    SPEED_KILOMETERS_PER_HOUR,
    LENGTH_KILOMETERS,
    LENGTH_MILLIMETERS,
)

from homeassistant.helpers.typing import ConfigType, HomeAssistantType

from .const import (
    ATTRIBUTION,
    DOMAIN,
    DWDWEATHER_DATA,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistantType, entry: ConfigType, async_add_entities
) -> None:
    """Add a weather entity from a config_entry."""
    hass_data = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([DWDWeather(entry.data, hass_data)], False)


class DWDWeather(DWDWeatherEntity, WeatherEntity):
    """Implementation of DWD weather."""

    def __init__(self, entry_data, hass_data):
        """Initialise the platform with a data instance and site."""

        dwd_data: DWDWeatherData = hass_data[DWDWEATHER_DATA]
        name = f"{dwd_data.dwd_weather.station_name}"
        unique_id = f"{dwd_data.dwd_weather.station_id}_weather"
        super().__init__(hass_data, unique_id, name)

    async def async_added_to_hass(self):
        """When entity is added to hass."""
        self.async_on_remove(
            self._coordinator.async_add_listener(self.async_write_ha_state)
        )

    async def async_update(self):
        """Schedule a custom update via the common entity update service."""
        await self._coordinator.async_request_refresh()

    @property
    def condition(self):
        """Return the current condition."""
        return self._connector.get_condition()

    @property
    def native_temperature(self):
        """Return the temperature."""
        return self._connector.get_temperature()

    @property
    def native_temperature_unit(self):
        """Return the temperature unit."""
        return TEMP_CELSIUS

    @property
    def native_pressure(self):
        """Return the pressure."""
        return self._connector.get_pressure()

    @property
    def native_pressure_unit(self):
        """Return the pressure unit."""
        return PRESSURE_HPA

    @property
    def native_wind_speed(self):
        """Return the wind speed."""
        return self._connector.get_wind_speed()

    @property
    def native_wind_speed_unit(self):
        """Return the wind speed unit."""
        return SPEED_KILOMETERS_PER_HOUR

    @property
    def wind_bearing(self):
        """Return the wind direction."""
        return self._connector.get_wind_direction()

    @property
    def native_visibility(self):
        """Return the visibility."""
        return self._connector.get_visibility()

    @property
    def native_visibility_unit(self):
        """Return the visibility unit."""
        return LENGTH_KILOMETERS

    @property
    def humidity(self):
        """Return the relative humidity."""
        return self._connector.get_humidity()

    @property
    def native_precipitation_unit(self):
        """Return the precipitation unit."""
        return LENGTH_MILLIMETERS

    @property
    def attribution(self):
        """Return the attribution."""
        return ATTRIBUTION

    @property
    def forecast(self):
        """Return the forecast array."""
        return self._connector.forecast

    @property
    def extra_state_attributes(self):
        """Return data validity infos."""
        return self._connector.infos
