"""Config flow for Deutscher Wetterdienst integration."""

import logging
import uuid
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.selector import (
    BooleanSelector,
    SelectSelector,
    TextSelector,
    LocationSelector,
    NumberSelector,
    ColorRGBSelector,
)
from simple_dwd_weatherforecast import dwdforecast

from .const import (
    CONF_ADDITIONAL_FORECAST_ATTRIBUTES,
    CONF_DAILY_TEMP_HIGH_PRECISION,
    CONF_DATA_TYPE,
    CONF_DATA_TYPE_FORECAST,
    CONF_DATA_TYPE_MIXED,
    CONF_DATA_TYPE_REPORT,
    CONF_ENTITY_TYPE,
    CONF_ENTITY_TYPE_MAP,
    CONF_ENTITY_TYPE_STATION,
    CONF_HOURLY_UPDATE,
    CONF_INTERPOLATE,
    CONF_SENSOR_FORECAST_STEPS,
    CONF_LOCATION_COORDINATES,
    CONF_CUSTOM_LOCATION,
    CONF_MAP_BACKGROUND_TYPE,
    CONF_MAP_DARK_MODE,
    CONF_MAP_FOREGROUND_MAXTEMP,
    CONF_MAP_FOREGROUND_POLLENFLUG,
    CONF_MAP_FOREGROUND_PRECIPITATION,
    CONF_MAP_FOREGROUND_SATELLITE_IR,
    CONF_MAP_FOREGROUND_SATELLITE_RGB,
    CONF_MAP_FOREGROUND_TYPE,
    CONF_MAP_FOREGROUND_UVINDEX,
    CONF_MAP_FOREGROUND_WARNUNGEN_GEMEINDEN,
    CONF_MAP_FOREGROUND_WARNUNGEN_KREISE,
    CONF_MAP_BACKGROUND_LAENDER,
    CONF_MAP_BACKGROUND_BUNDESLAENDER,
    CONF_MAP_BACKGROUND_KREISE,
    CONF_MAP_BACKGROUND_GEMEINDEN,
    CONF_MAP_BACKGROUND_SATELLIT,
    CONF_MAP_HOMEMARKER,
    CONF_MAP_HOMEMARKER_COLOR,
    CONF_MAP_HOMEMARKER_SHAPE,
    CONF_MAP_HOMEMARKER_SHAPE_CROSS,
    CONF_MAP_HOMEMARKER_SHAPE_SQUARE,
    CONF_MAP_HOMEMARKER_SIZE,
    CONF_MAP_ID,
    CONF_MAP_LOOP_COUNT,
    CONF_MAP_LOOP_SPEED,
    CONF_MAP_CENTERMARKER,
    CONF_MAP_TIMESTAMP,
    CONF_MAP_TYPE,
    CONF_MAP_TYPE_CUSTOM,
    CONF_MAP_TYPE_GERMANY,
    CONF_MAP_WINDOW,
    CONF_STATION_ID,
    CONF_STATION_NAME,
    DOMAIN,
    CONF_VERSION,
    CONF_WIND_DIRECTION_TYPE,
    conversion_table_map_foreground,
    CONF_MAP_HOMEMARKER_SHAPE_CIRCLE,
)

_LOGGER = logging.getLogger(__name__)


class DWDWeatherConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for DWD weather integration."""

    VERSION = CONF_VERSION
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        self.config_data = {}
        data_schema = vol.Schema({})
        _LOGGER.debug("User:user_input: {}".format(user_input))
        if user_input is not None:
            # Error in user input
            if len(errors) > 0:
                _LOGGER.debug("error: {}".format(errors))
                return self.async_show_form(
                    step_id="user",
                    data_schema=data_schema,
                    errors={errors},  # type: ignore
                )
            self.config_data.update(user_input)
            # Check selected option
            if user_input[CONF_ENTITY_TYPE] == CONF_ENTITY_TYPE_STATION:
                # Show station config form
                _LOGGER.debug("Selected weather_station")
                return await self.async_step_station_select()
            elif user_input[CONF_ENTITY_TYPE] == CONF_ENTITY_TYPE_MAP:
                self.config_data[CONF_MAP_ID] = str(uuid.uuid4()).upper()[:4]
                return await self.async_step_select_map_type()

        data_schema = vol.Schema(
            {
                vol.Required(
                    CONF_ENTITY_TYPE,
                    default=CONF_ENTITY_TYPE_STATION,  # type: ignore
                ): SelectSelector(
                    {
                        "options": list(
                            [CONF_ENTITY_TYPE_STATION, CONF_ENTITY_TYPE_MAP]
                        ),
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
            if station_data:
                stations.append(
                    {
                        "label": f"[{'X' if station_data['report_available'] == 1 else '_'}] {station[1]} km: {station_data['name']} (H:{station_data['elev']}m)",
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
                    default=False,  # type: ignore
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
                    default=CONF_DATA_TYPE_MIXED,  # type: ignore
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
        station = dwdforecast.load_station_id(self.config_data[CONF_STATION_ID])
        if station:
            data_schema = vol.Schema(
                {
                    vol.Required(
                        CONF_STATION_NAME,
                        default=station["name"],
                    ): TextSelector({}),
                    vol.Required(
                        CONF_WIND_DIRECTION_TYPE,
                        default="degrees",  # type: ignore
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
                        default=True,  # type: ignore
                    ): BooleanSelector({}),
                    vol.Required(
                        CONF_HOURLY_UPDATE,
                        default=False,  # type: ignore
                    ): BooleanSelector({}),
                    vol.Required(
                        CONF_SENSOR_FORECAST_STEPS,
                        default=250,  # type: ignore
                    ): NumberSelector({"min": 1, "max": 250, "step": 1, "mode": "box"}),
                    vol.Required(
                        CONF_ADDITIONAL_FORECAST_ATTRIBUTES,
                        default=False,  # type: ignore
                    ): BooleanSelector({}),
                    vol.Required(
                        CONF_DAILY_TEMP_HIGH_PRECISION,
                        default=False,  # type: ignore
                    ): BooleanSelector({}),
                }
            )

        return self.async_show_form(
            step_id="station_configure", data_schema=data_schema, errors=errors
        )

    async def async_step_select_map_type(self, user_input=None):
        errors = {}
        _LOGGER.debug("Map:user_input: {}".format(user_input))
        if user_input is not None:
            self.config_data.update(user_input)
            if user_input[CONF_MAP_TYPE] == CONF_MAP_TYPE_CUSTOM:
                return await self.async_step_select_map_window()
            elif user_input[CONF_MAP_TYPE] == CONF_MAP_TYPE_GERMANY:
                return await self.async_step_select_map_content()

        data_schema = vol.Schema(
            {
                vol.Required(
                    CONF_MAP_TYPE,
                    default=CONF_MAP_TYPE_GERMANY,  # type: ignore
                ): SelectSelector(
                    {
                        "options": list(
                            [
                                CONF_MAP_TYPE_GERMANY,
                                CONF_MAP_TYPE_CUSTOM,
                            ]
                        ),
                        "custom_value": False,
                        "mode": "list",
                        "translation_key": CONF_MAP_TYPE,
                    }
                )
            }
        )

        return self.async_show_form(
            step_id="select_map_type", data_schema=data_schema, errors=errors
        )

    async def async_step_select_map_window(self, user_input=None):
        errors = {}
        _LOGGER.debug("Map_window:user_input: {}".format(user_input))
        if user_input is not None:
            user_input["map_window"]["latitude"] = round(
                user_input["map_window"]["latitude"], 2
            )
            user_input["map_window"]["longitude"] = round(
                user_input["map_window"]["longitude"], 2
            )
            if "radius" in user_input["map_window"]:
                user_input["map_window"]["radius"] = round(
                    user_input["map_window"]["radius"] / 1000, 0
                )
            else:
                user_input["map_window"]["radius"] = 100
            self.config_data.update(user_input)
            return await self.async_step_select_map_content()

        data_schema = vol.Schema(
            {vol.Optional(CONF_MAP_WINDOW): LocationSelector({"radius": True})}
        )
        _LOGGER.debug("Map_window:user_input:error {}".format(errors))
        return self.async_show_form(
            step_id="select_map_window", data_schema=data_schema, errors=errors
        )

    async def async_step_select_map_content(self, user_input=None):
        errors = {}
        _LOGGER.debug("Map_content:user_input: {}".format(user_input))
        if user_input is not None:
            self.config_data.update(user_input)

            if (
                user_input[CONF_MAP_FOREGROUND_TYPE]
                == CONF_MAP_FOREGROUND_PRECIPITATION
            ):
                return await self.async_step_select_map_loop()
            else:
                if user_input[CONF_MAP_HOMEMARKER]:
                    return await self.async_step_select_map_homemarker()
                else:
                    return self.async_create_entry(
                        title=f"Weathermap {conversion_table_map_foreground[self.config_data[CONF_MAP_FOREGROUND_TYPE]]}",
                        data=self.config_data,
                    )

        data_schema = vol.Schema(
            {
                vol.Required(
                    CONF_MAP_FOREGROUND_TYPE,
                    default=CONF_MAP_FOREGROUND_PRECIPITATION,  # type: ignore
                ): SelectSelector(
                    {
                        "options": list(
                            [
                                CONF_MAP_FOREGROUND_PRECIPITATION,
                                CONF_MAP_FOREGROUND_MAXTEMP,
                                CONF_MAP_FOREGROUND_UVINDEX,
                                CONF_MAP_FOREGROUND_POLLENFLUG,
                                CONF_MAP_FOREGROUND_SATELLITE_RGB,
                                CONF_MAP_FOREGROUND_SATELLITE_IR,
                                CONF_MAP_FOREGROUND_WARNUNGEN_GEMEINDEN,
                                CONF_MAP_FOREGROUND_WARNUNGEN_KREISE,
                            ]
                        ),
                        "custom_value": False,
                        "mode": "dropdown",
                        "translation_key": CONF_MAP_FOREGROUND_TYPE,
                    }
                ),
                vol.Required(
                    CONF_MAP_BACKGROUND_TYPE,
                    default=CONF_MAP_BACKGROUND_BUNDESLAENDER,  # type: ignore
                ): SelectSelector(
                    {
                        "options": list(
                            [
                                CONF_MAP_BACKGROUND_LAENDER,
                                CONF_MAP_BACKGROUND_BUNDESLAENDER,
                                CONF_MAP_BACKGROUND_KREISE,
                                CONF_MAP_BACKGROUND_GEMEINDEN,
                                CONF_MAP_BACKGROUND_SATELLIT,
                            ]
                        ),
                        "custom_value": False,
                        "mode": "dropdown",
                        "translation_key": CONF_MAP_BACKGROUND_TYPE,
                    }
                ),
                vol.Required(
                    CONF_MAP_CENTERMARKER,
                    default=False,  # type: ignore
                ): BooleanSelector({}),
                vol.Required(
                    CONF_MAP_HOMEMARKER,
                    default=False,
                ): BooleanSelector({}),
                vol.Required(
                    CONF_MAP_DARK_MODE,
                    default=False,
                ): BooleanSelector({}),
            }
        )

        return self.async_show_form(
            step_id="select_map_content", data_schema=data_schema, errors=errors
        )

    async def async_step_select_map_loop(self, user_input=None):
        errors = {}
        _LOGGER.debug("Map_loop:user_input: {}".format(user_input))
        if user_input is not None:
            user_input[CONF_MAP_LOOP_COUNT] = int(user_input[CONF_MAP_LOOP_COUNT] / 5)
            self.config_data.update(user_input)

            if (
                CONF_MAP_HOMEMARKER in self.config_data
                and self.config_data[CONF_MAP_HOMEMARKER]
            ):
                return await self.async_step_select_map_homemarker()
            else:
                return self.async_create_entry(
                    title=f"Weathermap {conversion_table_map_foreground[self.config_data[CONF_MAP_FOREGROUND_TYPE]]}",
                    data=self.config_data,
                )

        data_schema = vol.Schema(
            {
                vol.Required(
                    CONF_MAP_TIMESTAMP,
                    default=False,  # type: ignore
                ): BooleanSelector({}),
                vol.Required(
                    CONF_MAP_LOOP_COUNT,
                    default=30,  # type: ignore
                ): NumberSelector(
                    {
                        "min": 5,
                        "max": 60,
                        "step": "5",
                        "mode": "slider",
                        "unit_of_measurement": "min",
                    }
                ),
                vol.Required(
                    CONF_MAP_LOOP_SPEED,
                    default=0.5,  # type: ignore
                ): NumberSelector(
                    {
                        "min": 0.1,
                        "max": 2,
                        "step": "0.1",
                        "mode": "slider",
                        "unit_of_measurement": "s",
                    }
                ),
            }
        )

        return self.async_show_form(
            step_id="select_map_loop", data_schema=data_schema, errors=errors
        )

    async def async_step_select_map_homemarker(self, user_input=None):
        errors = {}
        _LOGGER.debug("Map_window:user_input: {}".format(user_input))
        if user_input is not None:
            self.config_data.update(user_input)
            return self.async_create_entry(
                title=f"Weathermap {conversion_table_map_foreground[self.config_data[CONF_MAP_FOREGROUND_TYPE]]}",
                data=self.config_data,
            )

        data_schema = vol.Schema(
            {
                vol.Required(
                    CONF_MAP_HOMEMARKER_SHAPE,
                    default=CONF_MAP_HOMEMARKER_SHAPE_CIRCLE,
                ): SelectSelector(
                    {
                        "options": list(
                            [
                                CONF_MAP_HOMEMARKER_SHAPE_CIRCLE,
                                CONF_MAP_HOMEMARKER_SHAPE_CROSS,
                                CONF_MAP_HOMEMARKER_SHAPE_SQUARE,
                            ]
                        ),
                        "custom_value": False,
                        "mode": "dropdown",
                        "translation_key": CONF_MAP_HOMEMARKER_SHAPE,
                    }
                ),
                vol.Required(
                    CONF_MAP_HOMEMARKER_SIZE,
                    default=10,
                ): NumberSelector(
                    {
                        "min": 1,
                        "max": 25,
                        "step": "1",
                        "unit_of_measurement": "px",
                    }
                ),
                vol.Required(
                    CONF_MAP_HOMEMARKER_COLOR,
                    default=[255, 0, 0],
                ): ColorRGBSelector({}),
            }
        )
        _LOGGER.debug("Map_homemarker:user_input:error {}".format(errors))
        return self.async_show_form(
            step_id="select_map_homemarker", data_schema=data_schema, errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Create the options flow."""
        return OptionsFlowHandler()


class OptionsFlowHandler(config_entries.OptionsFlow):
    config_data = {}

    async def async_step_init(self, user_input: dict[str] | None = None) -> FlowResult:  # type: ignore
        """Manage the options."""
        if self.config_entry.data[CONF_ENTITY_TYPE] == CONF_ENTITY_TYPE_STATION:
            if user_input is not None:
                _LOGGER.debug(
                    "OptionsFlowHandler station: user_input {}".format(user_input)
                )

                user_input[CONF_ENTITY_TYPE] = self.config_entry.data[CONF_ENTITY_TYPE]
                user_input[CONF_STATION_ID] = self.config_entry.data[CONF_STATION_ID]
                user_input[CONF_STATION_NAME] = self.config_entry.data[
                    CONF_STATION_NAME
                ]
                user_input[CONF_CUSTOM_LOCATION] = self.config_entry.data[
                    CONF_CUSTOM_LOCATION
                ]
                self.hass.config_entries.async_update_entry(
                    self.config_entry,
                    data=user_input,
                    options=self.config_entry.options,
                )
                return self.async_create_entry(title="", data=user_input)

            return self.async_show_form(
                step_id="init",
                data_schema=vol.Schema(
                    {
                        vol.Required(
                            CONF_DATA_TYPE,
                            default=self.config_entry.data[CONF_DATA_TYPE],
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
                        ),
                        vol.Required(
                            CONF_WIND_DIRECTION_TYPE,
                            default=self.config_entry.data[CONF_WIND_DIRECTION_TYPE],
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
                            default=self.config_entry.data[CONF_INTERPOLATE],
                        ): BooleanSelector({}),
                        vol.Required(
                            CONF_HOURLY_UPDATE,
                            default=self.config_entry.data[CONF_HOURLY_UPDATE],
                        ): BooleanSelector({}),
                        vol.Required(
                            CONF_SENSOR_FORECAST_STEPS,
                            default=self.config_entry.data[CONF_SENSOR_FORECAST_STEPS],
                        ): NumberSelector(
                            {"min": 1, "max": 250, "step": 1, "mode": "box"}
                        ),
                        vol.Required(
                            CONF_ADDITIONAL_FORECAST_ATTRIBUTES,
                            default=self.config_entry.data[
                                CONF_ADDITIONAL_FORECAST_ATTRIBUTES
                            ],
                        ): BooleanSelector({}),
                        vol.Required(
                            CONF_DAILY_TEMP_HIGH_PRECISION,
                            default=self.config_entry.data[
                                CONF_DAILY_TEMP_HIGH_PRECISION
                            ],  # type: ignore
                        ): BooleanSelector({}),
                    }
                ),
            )  # type: ignore
        elif self.config_entry.data[CONF_ENTITY_TYPE] == CONF_ENTITY_TYPE_MAP:
            if user_input is not None:
                _LOGGER.debug(
                    "OptionsFlowHandler map: user_input {}".format(user_input)
                )

                user_input[CONF_ENTITY_TYPE] = self.config_entry.data[CONF_ENTITY_TYPE]
                user_input[CONF_MAP_ID] = self.config_entry.data[CONF_MAP_ID]
                user_input[CONF_MAP_FOREGROUND_TYPE] = self.config_entry.data[
                    CONF_MAP_FOREGROUND_TYPE
                ]
                if CONF_MAP_TYPE in self.config_entry.data:
                    user_input[CONF_MAP_TYPE] = self.config_entry.data[CONF_MAP_TYPE]
                if CONF_MAP_WINDOW in self.config_entry.data:
                    user_input[CONF_MAP_WINDOW] = self.config_entry.data[
                        CONF_MAP_WINDOW
                    ]
                if CONF_MAP_LOOP_COUNT in user_input:
                    user_input[CONF_MAP_LOOP_COUNT] = int(
                        user_input[CONF_MAP_LOOP_COUNT] / 5
                    )
                if user_input[CONF_MAP_HOMEMARKER]:
                    self.config_data.update(user_input)
                    return await self.async_step_homemarker()
                else:
                    self.hass.config_entries.async_update_entry(
                        self.config_entry,
                        data=user_input,
                        options=self.config_entry.options,
                    )
                    return self.async_create_entry(title="", data=user_input)
            data_schema = vol.Schema(
                {
                    vol.Required(
                        CONF_MAP_BACKGROUND_TYPE,
                        default=self.config_entry.data[CONF_MAP_BACKGROUND_TYPE],  # type: ignore
                    ): SelectSelector(
                        {
                            "options": list(
                                [
                                    CONF_MAP_BACKGROUND_LAENDER,
                                    CONF_MAP_BACKGROUND_BUNDESLAENDER,
                                    CONF_MAP_BACKGROUND_KREISE,
                                    CONF_MAP_BACKGROUND_GEMEINDEN,
                                    CONF_MAP_BACKGROUND_SATELLIT,
                                ]
                            ),
                            "custom_value": False,
                            "mode": "dropdown",
                            "translation_key": CONF_MAP_BACKGROUND_TYPE,
                        }
                    ),
                }
            )
            if (
                self.config_entry.data[CONF_MAP_FOREGROUND_TYPE]
                == CONF_MAP_FOREGROUND_PRECIPITATION
            ):
                data_schema = data_schema.extend(
                    {
                        vol.Required(
                            CONF_MAP_TIMESTAMP,
                            default=self.config_entry.data[CONF_MAP_TIMESTAMP],  # type: ignore
                        ): BooleanSelector({}),
                        vol.Required(
                            CONF_MAP_LOOP_COUNT,
                            default=self.config_entry.data[CONF_MAP_LOOP_COUNT] * 5,  # type: ignore
                        ): NumberSelector(
                            {
                                "min": 5,
                                "max": 60,
                                "step": "5",
                                "mode": "slider",
                                "unit_of_measurement": "min",
                            }
                        ),
                        vol.Required(
                            CONF_MAP_LOOP_SPEED,
                            default=self.config_entry.data[CONF_MAP_LOOP_SPEED],  # type: ignore
                        ): NumberSelector(
                            {
                                "min": 0.1,
                                "max": 2,
                                "step": "0.1",
                                "mode": "slider",
                                "unit_of_measurement": "s",
                            }
                        ),
                    }
                )
            data_schema = data_schema.extend(
                {
                    vol.Required(
                        CONF_MAP_CENTERMARKER,
                        default=self.config_entry.data[CONF_MAP_CENTERMARKER],  # type: ignore
                    ): BooleanSelector({}),
                    vol.Required(
                        CONF_MAP_HOMEMARKER,
                        default=self.config_entry.data[CONF_MAP_HOMEMARKER],
                    ): BooleanSelector({}),
                    vol.Required(
                        CONF_MAP_DARK_MODE,
                        default=self.config_entry.data[CONF_MAP_DARK_MODE],
                    ): BooleanSelector({}),
                }
            )
            return self.async_show_form(
                step_id="init",
                data_schema=data_schema,
            )

    async def async_step_homemarker(self, user_input=None) -> FlowResult:  # type: ignore
        """Manage the options for the homemarker."""
        if user_input is not None:
            _LOGGER.debug(
                "OptionsFlowHandler map marker: user_input {}".format(user_input)
            )
            self.config_data.update(user_input)
            self.hass.config_entries.async_update_entry(
                self.config_entry,
                data=self.config_data,
                options=self.config_entry.options,
            )
            return self.async_create_entry(title="", data=self.config_data)
        data_schema = vol.Schema(
            {
                vol.Required(
                    CONF_MAP_HOMEMARKER_SHAPE,
                    default=self.config_entry.data[CONF_MAP_HOMEMARKER_SHAPE]
                    if CONF_MAP_HOMEMARKER_SHAPE in self.config_entry.data
                    else CONF_MAP_HOMEMARKER_SHAPE_CIRCLE,
                ): SelectSelector(
                    {
                        "options": list(
                            [
                                CONF_MAP_HOMEMARKER_SHAPE_CIRCLE,
                                CONF_MAP_HOMEMARKER_SHAPE_CROSS,
                                CONF_MAP_HOMEMARKER_SHAPE_SQUARE,
                            ]
                        ),
                        "custom_value": False,
                        "mode": "dropdown",
                        "translation_key": CONF_MAP_HOMEMARKER_SHAPE,
                    }
                ),
                vol.Required(
                    CONF_MAP_HOMEMARKER_SIZE,
                    default=self.config_entry.data[CONF_MAP_HOMEMARKER_SIZE]
                    if CONF_MAP_HOMEMARKER_SIZE in self.config_entry.data
                    else 10,
                ): NumberSelector(
                    {
                        "min": 1,
                        "max": 25,
                        "step": "1",
                        "unit_of_measurement": "px",
                    }
                ),
                vol.Required(
                    CONF_MAP_HOMEMARKER_COLOR,
                    default=self.config_entry.data[CONF_MAP_HOMEMARKER_COLOR]
                    if CONF_MAP_HOMEMARKER_COLOR in self.config_entry.data
                    else [255, 0, 0],
                ): ColorRGBSelector({}),
            }
        )
        return self.async_show_form(
            step_id="homemarker",
            data_schema=data_schema,
        )
