"""Config flow for Deutscher Wetterdienst integration."""
import logging

import voluptuous as vol

from homeassistant import config_entries, core, exceptions
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE, CONF_NAME
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN

from .connector import DWDWeatherData

_LOGGER = logging.getLogger(__name__)


async def validate_input(hass: core.HomeAssistant, data):
    """Validate the user input 

    Data has the keys from DATA_SCHEMA with values provided by the user.
    """
    latitude = data[CONF_LATITUDE]
    longitude = data[CONF_LONGITUDE]

    dwd_weather_data = DWDWeatherData(hass, latitude, longitude)
    await dwd_weather_data.async_update()
    if dwd_weather_data.weather_data.get_station_name(False) == '':
        raise CannotConnect()

    return {"site_name": dwd_weather_data.weather_data.get_station_name(False)}


class DWDWeatherConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for DWD weather integration."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            await self.async_set_unique_id(
                f"{user_input[CONF_LATITUDE]}_{user_input[CONF_LONGITUDE]}")
            self._abort_if_unique_id_configured()

            try:
                info = await validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                user_input[CONF_NAME] = info["site_name"]
                return self.async_create_entry(title=user_input[CONF_NAME],
                                               data=user_input)

        data_schema = vol.Schema(
            {
                vol.Required(CONF_LATITUDE, default=self.hass.config.latitude):
                    cv.latitude,
                vol.Required(CONF_LONGITUDE, default=self.hass.config.longitude):
                    cv.longitude,
            },)

        return self.async_show_form(step_id="user",
                                    data_schema=data_schema,
                                    errors=errors)


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""
