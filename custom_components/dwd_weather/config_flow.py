"""Config flow for Deutscher Wetterdienst integration."""

import logging
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers.selector import (
    BooleanSelector,
    SelectSelector,
    TextSelector,
    LocationSelector,
)
from simple_dwd_weatherforecast import dwdforecast

from .const import (
    CONF_DATA_TYPE,
    CONF_DATA_TYPE_FORECAST,
    CONF_DATA_TYPE_MIXED,
    CONF_DATA_TYPE_REPORT,
    CONF_ENTITY_TYPE,
    CONF_ENTITY_TYPE_STATION,
    CONF_HOURLY_UPDATE,
    CONF_INTERPOLATE,
    CONF_LOCATION_COORDINATES,
    CONF_CUSTOM_LOCATION,
    CONF_STATION_ID,
    CONF_STATION_NAME,
    DOMAIN,
    CONF_WIND_DIRECTION_TYPE,
)

_LOGGER = logging.getLogger(__name__)


class DWDWeatherConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for DWD weather integration."""

    VERSION = 5
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
                    step_id="user", data_schema=data_schema, errors={errors}
                )
            # Check selected option
            if user_input[CONF_ENTITY_TYPE] == CONF_ENTITY_TYPE_STATION:
                # Show station config form
                _LOGGER.debug("Selected weather_station")
                return await self.async_step_station_select()
            else:
                pass

        data_schema = vol.Schema(
            {
                vol.Required(
                    CONF_ENTITY_TYPE,
                    default=CONF_ENTITY_TYPE_STATION,
                ): SelectSelector(
                    {
                        "options": list([CONF_ENTITY_TYPE_STATION]),
                        "custom_value": False,
                        "mode": "list",
                        "translation_key": CONF_ENTITY_TYPE,
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
            if user_input[CONF_CUSTOM_LOCATION]:
                _LOGGER.debug("Station:custom:")
                user_input[CONF_STATION_ID] = dwdforecast.get_nearest_station_id(
                    lat=user_input[CONF_LOCATION_COORDINATES]["latitude"],
                    lon=user_input[CONF_LOCATION_COORDINATES]["longitude"],
                )

            station = user_input[CONF_STATION_ID]

            _LOGGER.debug("Station:station id {}".format(station))
            station = dwdforecast.load_station_id(station)
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
                    "label": f"[{'X' if station_data['report_available'] == 1 else '_'}] {station[1]} km: {dwdforecast.load_station_id(station[0])['name']} (H:{station_data['elev']}m)",
                    "value": station[0],
                }
            )

        data_schema = vol.Schema(
            {
                vol.Required(
                    CONF_STATION_ID,
                    default=stations[0]["value"],
                ): SelectSelector(
                    {
                        "options": list(stations),
                        "custom_value": True,
                        "mode": "dropdown",
                    }
                ),
                vol.Required(
                    CONF_CUSTOM_LOCATION,
                    default=False,
                ): BooleanSelector({}),
                vol.Optional(CONF_LOCATION_COORDINATES): LocationSelector({}),
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
                    default=CONF_DATA_TYPE_MIXED,
                ): SelectSelector(
                    {
                        "options": list(
                            [
                                CONF_DATA_TYPE_MIXED,
                                CONF_DATA_TYPE_REPORT,
                                CONF_DATA_TYPE_FORECAST,
                            ]
                        ),
                        "custom_value": False,
                        "mode": "list",
                        "translation_key": CONF_DATA_TYPE,
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
                self.config_data[CONF_STATION_ID], user_input
            )
        )
        if user_input is not None:
            station_id = (
                f"{self.config_data[CONF_STATION_ID]}: {user_input[CONF_STATION_NAME]}"
            )
            if await self.async_set_unique_id(station_id) is not None:
                errors = {"base": "already_configured"}
            else:
                self.config_data.update(user_input)
                # The data is the data which is picked up by the async_setup_entry in sensor or weather
                return self.async_create_entry(title=station_id, data=self.config_data)

        _LOGGER.debug(
            "Station_configure:station_data: {}".format(
                dwdforecast.load_station_id(self.config_data[CONF_STATION_ID])
            )
        )
        data_schema = vol.Schema(
            {
                vol.Required(
                    CONF_STATION_NAME,
                    default=dwdforecast.load_station_id(
                        self.config_data[CONF_STATION_ID]
                    )["name"],
                ): TextSelector({}),
                vol.Required(
                    CONF_WIND_DIRECTION_TYPE,
                    default="degrees",
                ): SelectSelector(
                    {
                        "options": list(["degrees", "direction"]),
                        "custom_value": False,
                        "mode": "list",
                        "translation_key": CONF_WIND_DIRECTION_TYPE,
                    }
                ),
                vol.Required(
                    CONF_INTERPOLATE,
                    default=True,
                ): BooleanSelector({}),
                vol.Required(
                    CONF_HOURLY_UPDATE,
                    default=False,
                ): BooleanSelector({}),
            }
        )

        return self.async_show_form(
            step_id="station_configure", data_schema=data_schema, errors=errors
        )
