"""Support for DWD weather service."""

import logging
from custom_components.dwd_weather.connector import DWDWeatherData
from custom_components.dwd_weather.entity import DWDWeatherEntity

from homeassistant.components.weather import (
    WeatherEntity,
    Forecast,
)

from homeassistant.components.weather.const import (
    WeatherEntityFeature,
)

from homeassistant.const import (
    UnitOfLength,
    UnitOfPressure,
    UnitOfSpeed,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType

from .const import (
    ATTRIBUTION,
    CONF_STATION_ID,
    CONF_STATION_NAME,
    DOMAIN,
    DWDWEATHER_COORDINATOR,
    DWDWEATHER_DATA,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigType, async_add_entities
) -> None:
    """Add a weather entity from a config_entry."""
    hass_data = hass.data[DOMAIN][entry.entry_id]  # type: ignore
    if CONF_STATION_ID in entry.data:  # type: ignore
        async_add_entities([DWDWeather(entry.data, hass_data)], False)  # type: ignore


class DWDWeather(DWDWeatherEntity, WeatherEntity):
    """Implementation of DWD weather."""

    def __init__(self, entry_data, hass_data):
        """Initialise the platform with a data instance and site."""

        self._dwd_data: DWDWeatherData = hass_data[DWDWEATHER_DATA]
        self._coordinator = hass_data[DWDWEATHER_COORDINATOR]
        self._dwd_data.register_entity(self)

        unique_id = f"{self._dwd_data._config[CONF_STATION_ID]}_{self._dwd_data._config[CONF_STATION_NAME]}_Weather"
        _LOGGER.debug("Setting up weather with id {}".format(unique_id))
        super().__init__(hass_data, unique_id)

    async def async_forecast_daily(self) -> list[Forecast] | None:
        """Return the daily forecast in native units."""
        return self._connector.get_forecast(WeatherEntityFeature.FORECAST_DAILY)

    async def async_forecast_hourly(self) -> list[Forecast] | None:
        """Return the hourly forecast in native units."""
        return self._connector.get_forecast(WeatherEntityFeature.FORECAST_HOURLY)

    @property
    def name(self):
        """Return the name of the sensor."""
        return None

    @property
    def condition(self):
        """Return the current condition."""
        return self._connector.get_condition()

    @property
    def supported_features(self):
        """Return the current condition."""
        return (
            WeatherEntityFeature.FORECAST_HOURLY | WeatherEntityFeature.FORECAST_DAILY
        )

    @property
    def native_temperature(self):
        """Return the temperature."""
        return self._connector.get_temperature()

    @property
    def native_temperature_unit(self):
        """Return the temperature unit."""
        return UnitOfTemperature.CELSIUS

    @property
    def native_pressure(self):
        """Return the pressure."""
        return self._connector.get_pressure()

    @property
    def native_pressure_unit(self):
        """Return the pressure unit."""
        return UnitOfPressure.HPA

    @property
    def native_wind_speed(self):
        """Return the wind speed."""
        return self._connector.get_wind_speed()

    @property
    def native_wind_speed_unit(self):
        """Return the wind speed unit."""
        return UnitOfSpeed.KILOMETERS_PER_HOUR

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
        return UnitOfLength.KILOMETERS

    @property
    def humidity(self):
        """Return the relative humidity."""
        return self._connector.get_humidity()

    @property
    def native_precipitation_unit(self):
        """Return the precipitation unit."""
        return UnitOfLength.MILLIMETERS

    @property
    def uv_index(self):
        """Return the uv index."""
        return self._connector.get_uv_index()

    @property
    def attribution(self):
        """Return the attribution."""
        return ATTRIBUTION

    @property
    def extra_state_attributes(self):
        """Return data validity infos."""
        return self._connector.infos

    async def async_added_to_hass(self) -> None:
        """Connect to dispatcher listening for entity data notifications."""
        self.async_on_remove(
            self._coordinator.async_add_listener(self.async_write_ha_state)
        )
