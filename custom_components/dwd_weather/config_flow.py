"""Config flow for Deutscher Wetterdienst integration."""

import logging

import voluptuous as vol
from homeassistant import config_entries, core, exceptions
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE, CONF_NAME
from homeassistant.helpers import config_validation as cv

from .connector import DWDWeatherData
from .const import (
    CONF_STATION_ID,
    DOMAIN,
    CONF_WEATHER_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)


async def validate_input(hass: core.HomeAssistant, data):
    """Validate the user input

    Data has the keys from DATA_SCHEMA with values provided by the user.
    """
    latitude = data[CONF_LATITUDE]
    longitude = data[CONF_LONGITUDE]
    weather_interval = data[CONF_WEATHER_INTERVAL]
    station_id = data[CONF_STATION_ID]
    _LOGGER.debug(
        "validate_input:: CONF_LATITUDE: {}, CONF_LONGITUDE: {}, CONF_WEATHER_INTERVAL: {}, CONF_STATION_ID: {}".format(
            latitude, longitude, weather_interval, station_id
        )
    )
    if weather_interval > 24:
        raise WeatherIntervalTooBig()
    if 24 % weather_interval != 0:
        raise WeatherIntervalRemainderNotZero()

    dwd_weather_data = DWDWeatherData(
        hass, latitude, longitude, station_id, weather_interval
    )
    _LOGGER.debug(
        "Initialized new DWDWeatherData with id: {}".format(dwd_weather_data.station_id)
    )
    await dwd_weather_data.async_update()
    if dwd_weather_data.dwd_weather.get_station_name(False) == "":
        raise CannotConnect()

    return {"site_name": dwd_weather_data.dwd_weather.get_station_name(False).title()}


class DWDWeatherConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for DWD weather integration."""

    VERSION = 2
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        if user_input is not None:

            try:
                info = await validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except ValueError:
                errors["base"] = "invalid_station_id"
            except WeatherIntervalTooBig:
                errors["base"] = "weather_interval_too_big"
            except WeatherIntervalRemainderNotZero:
                errors["base"] = "weather_interval_remainder_not_zero"

            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                user_input[CONF_NAME] = info["site_name"]
                await self.async_set_unique_id(f"{user_input[CONF_NAME].lower()}")
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=user_input[CONF_NAME].title(), data=user_input
                )

        data_schema = vol.Schema(
            {
                vol.Required(
                    CONF_LATITUDE, default=self.hass.config.latitude
                ): cv.latitude,
                vol.Required(
                    CONF_LONGITUDE, default=self.hass.config.longitude
                ): cv.longitude,
                vol.Required(CONF_WEATHER_INTERVAL, default=24): cv.positive_int,
                vol.Optional(CONF_STATION_ID, default=""): str,
            },
        )

        return self.async_show_form(
            step_id="user", data_schema=data_schema, errors=errors
        )


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""


class WeatherIntervalTooBig(exceptions.HomeAssistantError):
    """Error to indicate only values to 24 are allowed."""


class WeatherIntervalRemainderNotZero(exceptions.HomeAssistantError):
    """Error to indicate that the remainder of 24 divided by the value has to be zero."""
