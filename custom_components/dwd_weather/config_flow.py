"""Config flow for Deutscher Wetterdienst integration."""

import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries, core, exceptions
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE, CONF_NAME
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.selector import selector
from simple_dwd_weatherforecast import dwdforecast
from homeassistant.core import callback

from .connector import DWDWeatherData
from .const import (
    CONF_DATA_TYPE,
    CONF_ENTITY_TYPE,
    CONF_HOURLY_UPDATE,
    CONF_STATION_ID,
    CONF_STATION_NAME,
    DOMAIN,
    CONF_WIND_DIRECTION_TYPE,
)

_LOGGER = logging.getLogger(__name__)


class DWDWeatherConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for DWD weather integration."""

    VERSION = 4
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        self.config_data = {}
        _LOGGER.debug("User:user_input: {}".format(user_input))
        if user_input is not None:
            # Error in user input
            if len(errors) > 0:
                _LOGGER.debug("error: {}".format(errors))
                return self.async_show_form(
                    step_id="user", data_schema=data_schema, errors=errors
                )
            # Check selected option
            if user_input[CONF_ENTITY_TYPE] == "weather_station":
                # Show station config form
                _LOGGER.debug("Selected weather_station")
                return await self.async_step_station_select()
            elif user_input[CONF_ENTITY_TYPE] == "weather_map":
                # Show map config form
                return self.async_create_entry(
                    title="Weather Map Test", data=self.config_data
                )
                pass

        data_schema = vol.Schema(
            {
                vol.Required(
                    CONF_ENTITY_TYPE,
                    default="weather_station",
                ): selector(
                    {
                        "select": {
                            "options": list(["weather_station"]),  # , "weather_map"
                            "custom_value": False,
                            "mode": "list",
                            "translation_key": CONF_ENTITY_TYPE,
                        }
                    }
                )
            },
        )

        return self.async_show_form(
            step_id="user", data_schema=data_schema, errors=errors
        )

    async def async_step_station_select(self, user_input=None):
        errors = {}
        _LOGGER.debug("Station:user_input: {}".format(user_input))
        if user_input is not None:
            station = dwdforecast.load_station_id(user_input["station_id"])
            _LOGGER.debug("Station:validation: {}".format(station))
            if station is not None:
                if station["report_available"] == 1:
                    self.config_data.update(user_input)
                    return await self.async_step_station_configure_report()
                else:
                    self.config_data[CONF_DATA_TYPE] = "forecast_data"
                    self.config_data.update(user_input)
                    return await self.async_step_station_configure()
            else:
                errors = {"base": "invalid_station_id"}

        stations_list = dwdforecast.get_stations_sorted_by_distance(
            self.hass.config.latitude, self.hass.config.longitude
        )
        stations = []

        for station in stations_list:
            station_data = dwdforecast.load_station_id(station[0])
            stations.append(
                {
                    "label": f"{station[1]} km: {dwdforecast.load_station_id(station[0])['name']} ({station_data['elev']}m) — {'Report data available' if station_data['report_available'] == 1 else 'Only forecast'}",
                    "value": station[0],
                }
            )

        data_schema = vol.Schema(
            {
                vol.Required(
                    CONF_STATION_ID,
                    default=stations[0]["value"],
                ): selector(
                    {
                        "select": {
                            "options": list(stations),
                            "custom_value": True,
                            "mode": "dropdown",
                        }
                    }
                ),
            }
        )

        return self.async_show_form(
            step_id="station_select", data_schema=data_schema, errors=errors
        )

    async def async_step_station_configure_report(self, user_input=None):
        errors = {}
        _LOGGER.debug("Station:user_input: {}".format(user_input))
        _LOGGER.debug("Station:configdata: {}".format(self.config_data))
        if user_input is not None:
            self.config_data.update(user_input)
            return await self.async_step_station_configure()

        data_schema = vol.Schema(
            {
                vol.Required(
                    CONF_DATA_TYPE,
                    default="report_data",
                ): selector(
                    {
                        "select": {
                            "options": list(["report_data", "forecast_data"]),
                            "custom_value": False,
                            "mode": "list",
                            "translation_key": CONF_DATA_TYPE,
                        }
                    }
                )
            }
        )

        return self.async_show_form(
            step_id="station_configure_report", data_schema=data_schema, errors=errors
        )

    async def async_step_station_configure(self, user_input=None):
        errors = {}
        _LOGGER.debug(
            "Station_configure:id: {},user_input: {}".format(
                self.config_data["station_id"], user_input
            )
        )
        if user_input is not None:
            self.config_data.update(user_input)
            await self.async_set_unique_id(self.config_data[CONF_STATION_ID])
            self._abort_if_unique_id_configured()
            # The data is the data which is picked up by the async_setup_entry in sensor or weather
            return self.async_create_entry(
                title=self.config_data[CONF_STATION_ID], data=self.config_data
            )

        _LOGGER.debug(
            "Station_configure:station_data: {}".format(
                dwdforecast.load_station_id(self.config_data["station_id"])
            )
        )
        data_schema = vol.Schema(
            {
                vol.Required(
                    CONF_STATION_NAME,
                    default=dwdforecast.load_station_id(self.config_data["station_id"])[
                        "name"
                    ],
                ): str,
                vol.Required(
                    CONF_WIND_DIRECTION_TYPE,
                    default="degrees",
                ): selector(
                    {
                        "select": {
                            "options": list(["degrees", "direction"]),
                            "custom_value": False,
                            "mode": "list",
                            "translation_key": CONF_WIND_DIRECTION_TYPE,
                        }
                    }
                ),
                vol.Required(
                    CONF_HOURLY_UPDATE,
                    default=False,
                ): bool,
            }
        )

        return self.async_show_form(
            step_id="station_configure", data_schema=data_schema, errors=errors
        )
