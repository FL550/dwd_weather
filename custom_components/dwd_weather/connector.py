"""Connector class to retrieve data, which is use by the weather and sensor enities."""

import logging
from datetime import datetime, timedelta, timezone
import math
import time
import PIL
import PIL.ImageDraw
import PIL.ImageFont
from markdownify import markdownify
from homeassistant.config_entries import ConfigEntry
from io import BytesIO
import warnings

with warnings.catch_warnings():
    warnings.filterwarnings("ignore", category=SyntaxWarning)
    from suntimes import SunTimes

from homeassistant.components.weather import (
    ATTR_FORECAST_CONDITION,
    ATTR_FORECAST_NATIVE_PRECIPITATION,
    ATTR_FORECAST_NATIVE_TEMP,
    ATTR_FORECAST_NATIVE_TEMP_LOW,
    ATTR_FORECAST_NATIVE_DEW_POINT,
    ATTR_FORECAST_TIME,
    ATTR_FORECAST_WIND_BEARING,
    ATTR_FORECAST_NATIVE_WIND_SPEED,
    ATTR_FORECAST_PRECIPITATION_PROBABILITY,
    Forecast,
)

from homeassistant.components.weather.const import (
    ATTR_WEATHER_WIND_GUST_SPEED,
    ATTR_WEATHER_UV_INDEX,
    WeatherEntityFeature,
)

from simple_dwd_weatherforecast import dwdforecast, dwdmap
from simple_dwd_weatherforecast.dwdforecast import WeatherDataType
from simple_dwd_weatherforecast.dwdmap import MarkerShape

from .const import (
    ATTR_FORECAST_CLOUD_COVERAGE,
    ATTR_FORECAST_EVAPORATION,
    ATTR_FORECAST_FOG_PROBABILITY,
    ATTR_FORECAST_HUMIDITY,
    ATTR_FORECAST_HUMIDITY_ABSOLUTE,
    ATTR_FORECAST_PRECIPITATION_DURATION,
    ATTR_FORECAST_PRESSURE,
    ATTR_FORECAST_SUN_IRRADIANCE,
    ATTR_FORECAST_VISIBILITY,
    ATTR_ISSUE_TIME,
    ATTR_REPORT_ISSUE_TIME,
    ATTR_LATEST_UPDATE,
    ATTR_STATION_ID,
    ATTR_STATION_NAME,
    ATTR_FORECAST_SUN_DURATION,
    CONF_ADDITIONAL_FORECAST_ATTRIBUTES,
    CONF_DAILY_TEMP_HIGH_PRECISION,
    CONF_DATA_TYPE,
    CONF_DATA_TYPE_FORECAST,
    CONF_DATA_TYPE_MIXED,
    CONF_DATA_TYPE_REPORT,
    CONF_INTERPOLATE,
    CONF_MAP_BACKGROUND_TYPE,
    CONF_MAP_FOREGROUND_TYPE,
    CONF_MAP_HOMEMARKER_COLOR,
    CONF_MAP_HOMEMARKER_SHAPE,
    CONF_MAP_HOMEMARKER_SHAPE_CIRCLE,
    CONF_MAP_HOMEMARKER_SHAPE_CROSS,
    CONF_MAP_HOMEMARKER_SHAPE_SQUARE,
    CONF_MAP_HOMEMARKER_SIZE,
    CONF_MAP_LOOP_COUNT,
    CONF_MAP_CENTERMARKER,
    CONF_MAP_HOMEMARKER,
    CONF_MAP_TIMESTAMP,
    CONF_MAP_TYPE,
    CONF_MAP_TYPE_GERMANY,
    CONF_MAP_WINDOW,
    CONF_SENSOR_FORECAST_STEPS,
    CONF_STATION_ID,
    CONF_STATION_NAME,
    CONF_WIND_DIRECTION_TYPE,
    CONF_HOURLY_UPDATE,
    DEFAULT_WIND_DIRECTION_TYPE,
    CONF_MAP_DARK_MODE,
    CONF_MAP_FOREGROUND_PRECIPITATION,
    CONF_MAP_FOREGROUND_MAXTEMP,
    CONF_MAP_FOREGROUND_UVINDEX,
    CONF_MAP_FOREGROUND_POLLENFLUG,
    CONF_MAP_FOREGROUND_SATELLITE_RGB,
    CONF_MAP_FOREGROUND_SATELLITE_IR,
    CONF_MAP_FOREGROUND_WARNUNGEN_GEMEINDEN,
    CONF_MAP_FOREGROUND_WARNUNGEN_KREISE,
    CONF_MAP_BACKGROUND_LAENDER,
    CONF_MAP_BACKGROUND_BUNDESLAENDER,
    CONF_MAP_BACKGROUND_KREISE,
    CONF_MAP_BACKGROUND_GEMEINDEN,
    CONF_MAP_BACKGROUND_SATELLIT,
)

conversion_table_map_homemarker_shape = {
    CONF_MAP_HOMEMARKER_SHAPE_CIRCLE: MarkerShape.CIRCLE,
    CONF_MAP_HOMEMARKER_SHAPE_CROSS: MarkerShape.CROSS,
    CONF_MAP_HOMEMARKER_SHAPE_SQUARE: MarkerShape.SQUARE,
}

_LOGGER = logging.getLogger(__name__)


class DWDWeatherData:
    def __init__(self, hass, config_entry: ConfigEntry):
        """Initialize the data object."""
        self._config = config_entry.data
        self._hass = hass
        self.forecast = None
        self.latest_update = None
        self.infos = {}
        self.entities = []

        # Holds the current data from DWD
        self.dwd_weather = dwdforecast.Weather(self._config[CONF_STATION_ID])
        if self.dwd_weather.station:
            self.sun = SunTimes(
                self.dwd_weather.station["lon"],
                self.dwd_weather.station["lat"],
                int(self.dwd_weather.station["elev"]),
            )

    def register_entity(self, entity):
        self.entities.append(entity)

    async def async_update(self):
        """Async wrapper for update method."""
        if await self._hass.async_add_executor_job(self._update):
            for entity in self.entities:
                await entity.async_update_listeners(("daily", "hourly"))

    def _update(self):
        """Get the latest data from DWD."""
        timestamp = datetime.now(timezone.utc)
        if timestamp.minute % 10 == 0 or self.latest_update is None:
            _LOGGER.info("Updating {}".format(self._config[CONF_STATION_NAME]))
            current_hour_data = None
            if self._config[CONF_HOURLY_UPDATE]:
                if self.dwd_weather.forecast_data and self.dwd_weather.is_in_timerange(
                    timestamp
                ):
                    current_hour_data = self.dwd_weather.forecast_data[  # type: ignore
                        self.dwd_weather.strip_to_hour_str(timestamp)
                    ]
            self.dwd_weather.update(
                force_hourly=self._config[CONF_HOURLY_UPDATE],
                with_forecast=True,
                with_measurements=(
                    True
                    if self._config[CONF_DATA_TYPE] == CONF_DATA_TYPE_REPORT
                    or self._config[CONF_DATA_TYPE] == CONF_DATA_TYPE_MIXED
                    else False
                ),
                with_report=True,
                with_uv=True,
            )
            if self._config[
                CONF_HOURLY_UPDATE
            ] and not self.dwd_weather.is_in_timerange(timestamp):
                # Hacky workaround: as the hourly data does not provide a forecast for the actual hour, we have to clone the next hour and pretend we have a forecast
                first_date = datetime(
                    *(
                        time.strptime(
                            next(iter(self.dwd_weather.forecast_data)),  # type: ignore
                            "%Y-%m-%dT%H:%M:%S.%fZ",
                        )[0:6]
                    ),
                    0,
                    timezone.utc,
                )
                if self.dwd_weather.forecast_data:
                    # If this is the first update, we have to clone the next hour data to be used as current hour data
                    if current_hour_data is None:
                        current_hour_data = self.dwd_weather.forecast_data[
                            first_date.strftime("%Y-%m-%dT%H:00:00.000Z")
                        ]
                    self.dwd_weather.forecast_data[
                        (first_date - timedelta(hours=1)).strftime(
                            "%Y-%m-%dT%H:00:00.000Z"
                        )
                    ] = current_hour_data
                    self.dwd_weather.forecast_data.move_to_end(
                        (first_date - timedelta(hours=1)).strftime(
                            "%Y-%m-%dT%H:00:00.000Z"
                        ),
                        last=False,
                    )
                # Hacky workaround end

            self.infos[ATTR_LATEST_UPDATE] = timestamp
            self.latest_update = timestamp
            if (
                self._config[CONF_DATA_TYPE] == CONF_DATA_TYPE_REPORT
                or self._config[CONF_DATA_TYPE] == CONF_DATA_TYPE_MIXED
            ) and self.dwd_weather.report_data is not None:
                report_date_array = self.dwd_weather.report_data["date"].split(".")
                date = f"20{report_date_array[2]}-{report_date_array[1]}-{report_date_array[0]} {self.dwd_weather.report_data['time']}"
                self.infos[ATTR_REPORT_ISSUE_TIME] = date
            else:
                self.infos[ATTR_REPORT_ISSUE_TIME] = ""
            self.infos[ATTR_ISSUE_TIME] = self.dwd_weather.issue_time
            self.infos[ATTR_STATION_ID] = self._config[CONF_STATION_ID]
            self.infos[ATTR_STATION_NAME] = self._config[CONF_STATION_NAME]
            _LOGGER.debug("Forecast data {}".format(self.dwd_weather.forecast_data))
            return True
        else:
            return False

    def get_forecast(self, WeatherEntityFeature_FORECAST) -> list[Forecast] | None:
        if WeatherEntityFeature_FORECAST == WeatherEntityFeature.FORECAST_HOURLY:
            return self.get_forecast_hourly()
        elif WeatherEntityFeature_FORECAST == WeatherEntityFeature.FORECAST_DAILY:
            return self.get_forecast_daily()

    def get_forecast_hourly(self) -> list[Forecast] | None:
        weather_interval = 1
        now = datetime.now(timezone.utc)
        forecast_data = []
        if self.latest_update and self.dwd_weather.is_in_timerange(now):
            timestep = datetime(
                now.year,
                now.month,
                now.day,
                now.hour,
                tzinfo=timezone.utc,
            )

            for _ in range(0, 9):
                for _ in range(int(24 / weather_interval)):
                    condition = self.dwd_weather.get_timeframe_condition(
                        timestep,
                        weather_interval,
                        False,
                    )
                    if (
                        condition == "sunny"
                        and weather_interval < 4
                        and (
                            timestep.hour < self.sun.riseutc(timestep).hour  # type: ignore
                            or timestep.hour > self.sun.setutc(timestep).hour  # type: ignore
                        )
                    ):
                        condition = "clear-night"
                    temp_max = self.dwd_weather.get_timeframe_max(
                        WeatherDataType.TEMPERATURE,
                        timestep,
                        weather_interval,
                        False,
                    )

                    dew_point = self.dwd_weather.get_timeframe_max(
                        WeatherDataType.DEWPOINT,
                        timestep,
                        weather_interval,
                        False,
                    )

                    wind_dir = self.dwd_weather.get_timeframe_avg(
                        WeatherDataType.WIND_DIRECTION,
                        timestep,
                        weather_interval,
                        False,
                    )

                    if (
                        self._config[CONF_WIND_DIRECTION_TYPE]
                        != DEFAULT_WIND_DIRECTION_TYPE
                    ):
                        wind_dir = self.get_wind_direction_symbol(wind_dir)

                    precipitation_prop = self.dwd_weather.get_timeframe_max(
                        WeatherDataType.PRECIPITATION_PROBABILITY,
                        timestep,
                        weather_interval,
                        False,
                    )
                    if precipitation_prop is not None:
                        precipitation_prop = int(precipitation_prop)

                    uv_index = (
                        self.dwd_weather.get_uv_index(
                            timestep.day - now.day, shouldUpdate=False
                        )
                        if timestep.day - now.day >= 0 and timestep.day - now.day < 3
                        else None
                    )
                    wind_speed = self.dwd_weather.get_timeframe_max(
                        WeatherDataType.WIND_SPEED,
                        timestep,
                        weather_interval,
                        False,
                    )
                    wind_gusts = self.dwd_weather.get_timeframe_max(
                        WeatherDataType.WIND_GUSTS,
                        timestep,
                        weather_interval,
                        False,
                    )
                    pressure = self.dwd_weather.get_timeframe_max(
                        WeatherDataType.PRESSURE,
                        timestep,
                        weather_interval,
                        False,
                    )

                    data_item = {
                        ATTR_FORECAST_TIME: timestep.strftime("%Y-%m-%dT%H:00:00Z"),
                        ATTR_FORECAST_CLOUD_COVERAGE: self.dwd_weather.get_timeframe_max(
                            WeatherDataType.CLOUD_COVERAGE,
                            timestep,
                            weather_interval,
                            False,
                        ),
                        ATTR_FORECAST_CONDITION: condition,
                        ATTR_FORECAST_NATIVE_DEW_POINT: round(dew_point - 273.1, 1)
                        if dew_point is not None
                        else None,
                        ATTR_FORECAST_NATIVE_PRECIPITATION: self.dwd_weather.get_timeframe_sum(
                            WeatherDataType.PRECIPITATION,
                            timestep,
                            weather_interval,
                            False,
                        ),
                        ATTR_FORECAST_PRECIPITATION_PROBABILITY: precipitation_prop,
                        ATTR_FORECAST_PRESSURE: round(pressure / 100, 1)
                        if pressure is not None
                        else None,
                        ATTR_FORECAST_NATIVE_TEMP: round(temp_max - 273.1, 1)
                        if temp_max is not None
                        else None,
                        ATTR_WEATHER_UV_INDEX: uv_index,
                        ATTR_FORECAST_NATIVE_WIND_SPEED: (
                            round(wind_speed * 3.6, 1)
                            if wind_speed is not None
                            else None
                        ),
                        ATTR_WEATHER_WIND_GUST_SPEED: (
                            round(wind_gusts * 3.6, 1)
                            if wind_gusts is not None
                            else None
                        ),
                        ATTR_FORECAST_WIND_BEARING: wind_dir,
                    }
                    # Additional attributes raises errors when parsed in HA weather template so this has to be optional
                    if self._config[CONF_ADDITIONAL_FORECAST_ATTRIBUTES]:
                        temp_min = self.dwd_weather.get_timeframe_min(
                            WeatherDataType.TEMPERATURE,
                            timestep,
                            weather_interval,
                            False,
                        )
                        humidity = self.dwd_weather.get_timeframe_max(
                            WeatherDataType.HUMIDITY,
                            timestep,
                            weather_interval,
                            False,
                        )
                        if humidity is not None and temp_min is not None:
                            humidity_absolute = self.calculate_absolute_humidity(
                                temp_min - 273.15, humidity
                            )
                        data_item.update(
                            {
                                ATTR_FORECAST_EVAPORATION: self.dwd_weather.get_timeframe_max(
                                    WeatherDataType.EVAPORATION,
                                    timestep,
                                    weather_interval,
                                    False,
                                ),
                                ATTR_FORECAST_FOG_PROBABILITY: self.dwd_weather.get_timeframe_max(
                                    WeatherDataType.FOG_PROBABILITY,
                                    timestep,
                                    weather_interval,
                                    False,
                                ),
                                ATTR_FORECAST_SUN_IRRADIANCE: self.dwd_weather.get_timeframe_sum(
                                    WeatherDataType.SUN_IRRADIANCE,
                                    timestep,
                                    weather_interval,
                                    False,
                                ),
                                ATTR_FORECAST_VISIBILITY: self.dwd_weather.get_timeframe_min(
                                    WeatherDataType.VISIBILITY,
                                    timestep,
                                    weather_interval,
                                    False,
                                ),
                                ATTR_FORECAST_SUN_DURATION: self.dwd_weather.get_timeframe_sum(
                                    WeatherDataType.SUN_DURATION,
                                    timestep,
                                    weather_interval,
                                    False,
                                ),
                                ATTR_FORECAST_PRECIPITATION_DURATION: self.dwd_weather.get_timeframe_max(
                                    WeatherDataType.PRECIPITATION_DURATION,
                                    timestep,
                                    weather_interval,
                                    False,
                                ),
                                ATTR_FORECAST_HUMIDITY: humidity,
                                ATTR_FORECAST_HUMIDITY_ABSOLUTE: humidity_absolute,
                            }
                        )
                    forecast_data.append(data_item)
                    timestep += timedelta(hours=weather_interval)
        return forecast_data

    def get_forecast_daily(self) -> list[Forecast] | None:
        weather_interval = 24
        now = datetime.now(timezone.utc)
        forecast_data = []
        if self.latest_update and self.dwd_weather.is_in_timerange(now):
            timestep = datetime(
                now.year,
                now.month,
                now.day,
                tzinfo=timezone.utc,
            )

            for _ in range(0, 9):
                _LOGGER.debug("Timestep {}".format(timestep))
                condition = self.dwd_weather.get_daily_condition(
                    timestep,
                    False,
                )
                temp_max = self.dwd_weather.get_daily_max(
                    WeatherDataType.TEMPERATURE,
                    timestep,
                    False,
                )

                temp_min = self.dwd_weather.get_daily_min(
                    WeatherDataType.TEMPERATURE,
                    timestep,
                    False,
                )

                dew_point = self.dwd_weather.get_daily_max(
                    WeatherDataType.DEWPOINT,
                    timestep,
                    False,
                )

                wind_dir = self.dwd_weather.get_daily_avg(
                    WeatherDataType.WIND_DIRECTION,
                    timestep,
                    False,
                )

                if (
                    self._config[CONF_WIND_DIRECTION_TYPE]
                    != DEFAULT_WIND_DIRECTION_TYPE
                ):
                    wind_dir = self.get_wind_direction_symbol(wind_dir)

                precipitation_prop = self.dwd_weather.get_daily_max(
                    WeatherDataType.PRECIPITATION_PROBABILITY,
                    timestep,
                    False,
                )
                if precipitation_prop is not None:
                    precipitation_prop = int(precipitation_prop)

                uv_index = (
                    self.dwd_weather.get_uv_index(
                        timestep.day - now.day, shouldUpdate=False
                    )
                    if timestep.day - now.day >= 0 and timestep.day - now.day < 3
                    else None
                )
                wind_speed = self.dwd_weather.get_daily_max(
                    WeatherDataType.WIND_SPEED,
                    timestep,
                    False,
                )
                wind_gusts = self.dwd_weather.get_daily_max(
                    WeatherDataType.WIND_GUSTS,
                    timestep,
                    False,
                )
                pressure = self.dwd_weather.get_daily_max(
                    WeatherDataType.PRESSURE,
                    timestep,
                    False,
                )

                data_item = {
                    ATTR_FORECAST_TIME: timestep.strftime("%Y-%m-%dT%H:00:00Z"),
                    ATTR_FORECAST_CLOUD_COVERAGE: self.dwd_weather.get_daily_max(
                        WeatherDataType.CLOUD_COVERAGE,
                        timestep,
                        False,
                    ),
                    ATTR_FORECAST_CONDITION: condition,
                    ATTR_FORECAST_NATIVE_DEW_POINT: round(dew_point - 273.1, 1)
                    if dew_point is not None
                    else None,
                    ATTR_FORECAST_NATIVE_PRECIPITATION: self.dwd_weather.get_daily_sum(
                        WeatherDataType.PRECIPITATION,
                        timestep,
                        False,
                    ),
                    ATTR_FORECAST_PRECIPITATION_PROBABILITY: precipitation_prop,
                    ATTR_FORECAST_PRESSURE: round(pressure / 100, 1)
                    if pressure is not None
                    else None,
                    ATTR_FORECAST_NATIVE_TEMP: round(
                        temp_max - 273.1,
                        1 if self._config[CONF_DAILY_TEMP_HIGH_PRECISION] else 0,
                    )
                    if temp_max is not None
                    else None,
                    ATTR_FORECAST_NATIVE_TEMP_LOW: round(
                        temp_min - 273.1,
                        1 if self._config[CONF_DAILY_TEMP_HIGH_PRECISION] else 0,
                    )
                    if temp_min is not None
                    else None,
                    ATTR_WEATHER_UV_INDEX: uv_index,
                    ATTR_FORECAST_NATIVE_WIND_SPEED: (
                        round(wind_speed * 3.6, 1) if wind_speed is not None else None
                    ),
                    ATTR_WEATHER_WIND_GUST_SPEED: (
                        round(wind_gusts * 3.6, 1) if wind_gusts is not None else None
                    ),
                    ATTR_FORECAST_WIND_BEARING: wind_dir,
                }
                # Additional attributes raises errors when parsed in HA weather template so this has to be optional
                if self._config[CONF_ADDITIONAL_FORECAST_ATTRIBUTES]:
                    data_item.update(
                        {
                            ATTR_FORECAST_EVAPORATION: self.dwd_weather.get_daily_max(
                                WeatherDataType.EVAPORATION,
                                timestep,
                                False,
                            ),
                            ATTR_FORECAST_FOG_PROBABILITY: self.dwd_weather.get_daily_max(
                                WeatherDataType.FOG_PROBABILITY,
                                timestep,
                                False,
                            ),
                            ATTR_FORECAST_SUN_IRRADIANCE: self.dwd_weather.get_daily_sum(
                                WeatherDataType.SUN_IRRADIANCE,
                                timestep,
                                False,
                            ),
                            ATTR_FORECAST_VISIBILITY: self.dwd_weather.get_daily_min(
                                WeatherDataType.VISIBILITY,
                                timestep,
                                False,
                            ),
                            ATTR_FORECAST_SUN_DURATION: self.dwd_weather.get_daily_sum(
                                WeatherDataType.SUN_DURATION,
                                timestep,
                                False,
                            ),
                            ATTR_FORECAST_PRECIPITATION_DURATION: self.dwd_weather.get_daily_sum(
                                WeatherDataType.PRECIPITATION_DURATION,
                                timestep,
                                False,
                            ),
                            ATTR_FORECAST_HUMIDITY: self.dwd_weather.get_daily_max(
                                WeatherDataType.HUMIDITY,
                                timestep,
                                False,
                            ),
                        }
                    )
                forecast_data.append(data_item)
                timestep += timedelta(hours=weather_interval)
        _LOGGER.debug("Daily Forecast data {}".format(forecast_data))
        return forecast_data

    def get_condition(self):
        now = datetime.now(timezone.utc)
        condition = self.dwd_weather.get_forecast_condition(now, False)
        if condition == "sunny" and (
            now.hour < self.sun.riseutc(now).hour  # type: ignore
            or now.hour > self.sun.setutc(now).hour  # type: ignore
        ):
            condition = "clear-night"
        return condition

    def get_weather_report(self):
        report = self.dwd_weather.get_weather_report(shouldUpdate=False)
        return markdownify(report, strip=["br"]) if report is not None else None

    def get_weather_value(self, data_type: WeatherDataType):
        value = None
        conf_data_type = self._config[CONF_DATA_TYPE]
        if (
            conf_data_type == CONF_DATA_TYPE_REPORT
            or conf_data_type == CONF_DATA_TYPE_MIXED
        ):
            try:
                value = self.dwd_weather.get_reported_weather(
                    data_type,
                    shouldUpdate=False,
                )
            except Exception as e:
                _LOGGER.debug(f"Error getting reported weather: {e}")
        if conf_data_type == CONF_DATA_TYPE_FORECAST or (
            conf_data_type == CONF_DATA_TYPE_MIXED and value is None
        ):
            value = self.dwd_weather.get_forecast_data(
                data_type,
                datetime.now(timezone.utc),
                shouldUpdate=False,
            )

        if self._config[CONF_INTERPOLATE] and value is not None:
            now_time_actual = datetime.now(timezone.utc)
            next_value = self.dwd_weather.get_forecast_data(
                data_type,
                now_time_actual + timedelta(hours=1),
                shouldUpdate=False,
            )
            if next_value is not None:
                now_time_hour = self.dwd_weather.strip_to_hour(now_time_actual).replace(
                    tzinfo=timezone.utc
                )
                value = round(
                    value
                    + (
                        (next_value - value)
                        * ((now_time_actual - now_time_hour).seconds / 3600)
                    ),
                    2,
                )

        data_type_mapping = {
            WeatherDataType.TEMPERATURE: lambda x: round(x - 273.1, 1),
            WeatherDataType.DEWPOINT: lambda x: round(x - 273.1, 1),
            WeatherDataType.PRESSURE: lambda x: round(x / 100, 1),
            WeatherDataType.WIND_SPEED: lambda x: round(x * 3.6, 1),
            WeatherDataType.WIND_DIRECTION: lambda x: (
                round(x, 0)
                if self._config[CONF_WIND_DIRECTION_TYPE] == DEFAULT_WIND_DIRECTION_TYPE
                else self.get_wind_direction_symbol(round(x, 0))
            ),
            WeatherDataType.WIND_GUSTS: lambda x: round(x * 3.6, 1),
            WeatherDataType.PRECIPITATION: lambda x: round(x, 1),
            WeatherDataType.PRECIPITATION_PROBABILITY: lambda x: round(x, 0),
            WeatherDataType.PRECIPITATION_DURATION: lambda x: round(x, 0),
            WeatherDataType.CLOUD_COVERAGE: lambda x: round(x, 0),
            WeatherDataType.VISIBILITY: lambda x: round(x / 1000, 1),
            WeatherDataType.SUN_DURATION: lambda x: round(x, 0),
            WeatherDataType.SUN_IRRADIANCE: lambda x: round(x / 3.6, 0),
            WeatherDataType.FOG_PROBABILITY: lambda x: round(x, 0),
            WeatherDataType.HUMIDITY: lambda x: round(x, 1),
        }

        # Check if value is not None
        if value is not None:
            # Check if the data_type is in the dictionary
            if data_type in data_type_mapping:
                # Use the corresponding calculation from the dictionary
                value = data_type_mapping[data_type](value)

        return value

    def get_temperature(self):
        return self.get_weather_value(WeatherDataType.TEMPERATURE)

    def get_dewpoint(self):
        return self.get_weather_value(WeatherDataType.DEWPOINT)

    def get_pressure(self):
        return self.get_weather_value(WeatherDataType.PRESSURE)

    def get_wind_speed(self):
        return self.get_weather_value(WeatherDataType.WIND_SPEED)

    def get_wind_direction(self):
        return self.get_weather_value(WeatherDataType.WIND_DIRECTION)

    def get_wind_gusts(self):
        return self.get_weather_value(WeatherDataType.WIND_GUSTS)

    def get_precipitation(self):
        return self.get_weather_value(WeatherDataType.PRECIPITATION)

    def get_precipitation_probability(self):
        return self.get_weather_value(WeatherDataType.PRECIPITATION_PROBABILITY)

    def get_precipitation_duration(self):
        return self.get_weather_value(WeatherDataType.PRECIPITATION_DURATION)

    def get_cloud_coverage(self):
        return self.get_weather_value(WeatherDataType.CLOUD_COVERAGE)

    def get_visibility(self):
        return self.get_weather_value(WeatherDataType.VISIBILITY)

    def get_sun_duration(self):
        return self.get_weather_value(WeatherDataType.SUN_DURATION)

    def get_sun_irradiance(self):
        return self.get_weather_value(WeatherDataType.SUN_IRRADIANCE)

    def get_fog_probability(self):
        return self.get_weather_value(WeatherDataType.FOG_PROBABILITY)

    def get_humidity(self):
        return self.get_weather_value(WeatherDataType.HUMIDITY)

    def get_humidity_absolute(self):
        temperature = self.get_temperature()
        humidity = self.get_humidity()
        abs_hum = self.calculate_absolute_humidity(temperature, humidity)
        return abs_hum

    def get_uv_index(self):
        return self.dwd_weather.get_uv_index(days_from_today=0, shouldUpdate=False)

    def get_evaporation(self):
        # Evaporation is reported as "within the last 24 hours. Therefore we have to add a day in the request"
        return self.dwd_weather.get_daily_max(
            WeatherDataType.EVAPORATION,
            datetime.now() + timedelta(days=1),
            False,
        )

    def get_condition_hourly(self):
        data = []
        forecast_data = self.dwd_weather.forecast_data
        if forecast_data:
            for key in forecast_data:
                item = forecast_data[key][WeatherDataType.CONDITION.value[0]]
                value = self.dwd_weather.weather_codes[item][0] if item != "-" else None  # type: ignore
                data.append({ATTR_FORECAST_TIME: key, "value": value})
        return data

    def get_hourly(self, data_type: WeatherDataType):
        data = []
        timestamp = datetime.now(timezone.utc)
        timestamp = datetime(
            timestamp.year,
            timestamp.month,
            timestamp.day,
            timestamp.hour,
            tzinfo=timezone.utc,
        )
        forecast_data = self.dwd_weather.forecast_data

        conversion_table = {
            WeatherDataType.TEMPERATURE: lambda value: round(value - 273.1, 1),
            WeatherDataType.DEWPOINT: lambda value: round(value - 273.1, 1),
            WeatherDataType.PRESSURE: lambda value: round(value / 100, 1),
            WeatherDataType.WIND_SPEED: lambda value: round(value * 3.6, 1),
            WeatherDataType.WIND_DIRECTION: lambda value: (
                round(value, 0)
                if self._config[CONF_WIND_DIRECTION_TYPE] == DEFAULT_WIND_DIRECTION_TYPE
                else self.get_wind_direction_symbol(round(value, 0))
            ),
            WeatherDataType.WIND_GUSTS: lambda value: round(value * 3.6, 1),
            WeatherDataType.PRECIPITATION: lambda value: round(value, 1),
            WeatherDataType.PRECIPITATION_PROBABILITY: lambda value: round(value, 0),
            WeatherDataType.PRECIPITATION_DURATION: lambda value: round(value, 1),
            WeatherDataType.CLOUD_COVERAGE: lambda value: round(value, 0),
            WeatherDataType.VISIBILITY: lambda value: round(value / 1000, 1),
            WeatherDataType.SUN_DURATION: lambda value: round(value, 0),
            WeatherDataType.SUN_IRRADIANCE: lambda value: round(value / 3.6, 0),
            WeatherDataType.FOG_PROBABILITY: lambda value: round(value, 0),
            WeatherDataType.HUMIDITY: lambda value: round(value, 1),
        }
        if forecast_data:
            item_counter = 0
            for key in forecast_data:
                if (
                    self._config[CONF_SENSOR_FORECAST_STEPS]
                    and item_counter >= self._config[CONF_SENSOR_FORECAST_STEPS]
                ):
                    break
                if (
                    datetime(
                        *(time.strptime(key, "%Y-%m-%dT%H:%M:%S.%fZ")[0:6]),
                        0,
                        timezone.utc,
                    )
                    < timestamp
                ):
                    continue
                item_counter += 1
                item = forecast_data[key]
                value = item[data_type.value[0]]
                if value is not None:
                    if data_type in conversion_table:
                        value = conversion_table[data_type](value)
                data.append(
                    {
                        ATTR_FORECAST_TIME: key,
                        "value": value,
                    }
                )

        return data

    def get_temperature_hourly(self):
        return self.get_hourly(WeatherDataType.TEMPERATURE)

    def get_dewpoint_hourly(self):
        return self.get_hourly(WeatherDataType.DEWPOINT)

    def get_pressure_hourly(self):
        return self.get_hourly(WeatherDataType.PRESSURE)

    def get_wind_speed_hourly(self):
        return self.get_hourly(WeatherDataType.WIND_SPEED)

    def get_wind_direction_hourly(self):
        return self.get_hourly(WeatherDataType.WIND_DIRECTION)

    def get_wind_gusts_hourly(self):
        return self.get_hourly(WeatherDataType.WIND_GUSTS)

    def get_precipitation_hourly(self):
        return self.get_hourly(WeatherDataType.PRECIPITATION)

    def get_precipitation_probability_hourly(self):
        return self.get_hourly(WeatherDataType.PRECIPITATION_PROBABILITY)

    def get_precipitation_duration_hourly(self):
        return self.get_hourly(WeatherDataType.PRECIPITATION_DURATION)

    def get_cloud_coverage_hourly(self):
        return self.get_hourly(WeatherDataType.CLOUD_COVERAGE)

    def get_visibility_hourly(self):
        return self.get_hourly(WeatherDataType.VISIBILITY)

    def get_sun_duration_hourly(self):
        return self.get_hourly(WeatherDataType.SUN_DURATION)

    def get_sun_irradiance_hourly(self):
        return self.get_hourly(WeatherDataType.SUN_IRRADIANCE)

    def get_fog_probability_hourly(self):
        return self.get_hourly(WeatherDataType.FOG_PROBABILITY)

    def get_humidity_hourly(self):
        return self.get_hourly(WeatherDataType.HUMIDITY)

    def get_humidity_absolute_hourly(self):
        temperature = self.get_hourly(WeatherDataType.TEMPERATURE)
        humidity = self.get_hourly(WeatherDataType.HUMIDITY)
        absolute_humidity = []
        for temp, hum in zip(temperature, humidity):
            if temp["value"] is not None and hum["value"] is not None:
                abs_hum = self.calculate_absolute_humidity(temp["value"], hum["value"])
                absolute_humidity.append(
                    {
                        ATTR_FORECAST_TIME: temp[ATTR_FORECAST_TIME],
                        "value": abs_hum,
                    }
                )
        return absolute_humidity

    def get_uv_index_daily(self):
        return {
            "today": self.dwd_weather.get_uv_index(
                days_from_today=0, shouldUpdate=False
            ),
            "tomorrow": self.dwd_weather.get_uv_index(
                days_from_today=1, shouldUpdate=False
            ),
            "dayaftertomorrow": self.dwd_weather.get_uv_index(
                days_from_today=2, shouldUpdate=False
            ),
        }

    def get_evaporation_daily(self):
        data = []
        for i in range(9):
            timestamp = self.dwd_weather.issue_time + timedelta(days=1 + i)  # type: ignore
            timestamp = timestamp.replace(hour=6)
            evaporation = self.dwd_weather.get_daily_max(
                WeatherDataType.EVAPORATION,
                timestamp,
                False,
            )
            data.append(
                {
                    ATTR_FORECAST_TIME: timestamp - timedelta(days=1),
                    "value": evaporation,
                }
            )

        return data

    def get_wind_direction_symbol(self, value):
        if value is None:
            return ""
        elif value < 22.5:
            return "N"
        elif value < 67.5:
            return "NO"
        elif value < 112.5:
            return "O"
        elif value < 157.5:
            return "SO"
        elif value < 202.5:
            return "S"
        elif value < 247.5:
            return "SW"
        elif value < 292.5:
            return "W"
        elif value < 337.5:
            return "NW"
        else:
            return "N"

    def calculate_absolute_humidity(self, temperature, humidity) -> float:
        """Calculate absolute humidity from temperature and relative humidity."""
        # Constants for the calculation
        mw = 18.016  # molar mass of water g/mol
        r = 0.083143  # Universal gas constant

        abs_hum = round(
            (
                6.112
                * math.exp((17.67 * temperature) / (temperature + 243.5))
                * humidity
                * mw
            )
            / ((273.15 + temperature) * r * 100),
            1,
        )

        return abs_hum


class DWDMapData:
    def __init__(self, hass, config_entry: ConfigEntry):
        """Initialize the data object."""
        self._configentry = config_entry
        self._configdata = config_entry.data
        self._hass = hass
        self._image = None
        self._images = None

        self._width = None
        self._height = None
        self._maploop = None
        self._cachedheight = 0
        self._cachedwidth = 0
        self._image_nr = 0

    async def async_update(self):
        """Async wrapper for update method."""
        _LOGGER.debug("map async_update")
        return await self._hass.async_add_executor_job(self._update)

    def _update(self):
        if (
            self._configdata[CONF_MAP_FOREGROUND_TYPE]
            == CONF_MAP_FOREGROUND_PRECIPITATION
        ):
            self._update_loop()
        else:
            self._update_single()

    def _update_loop(self):
        _LOGGER.debug(
            "_update: {} w1 {} w2 {}, h1 {} h2 {}".format(
                self._maploop,
                self._width,
                self._cachedwidth,
                self._height,
                self._cachedheight,
            )
        )
        if (
            self._maploop
            and self._width == self._cachedwidth
            and self._height == self._cachedheight
            and self.last_config_change == self._configentry.modified_at
        ):
            _LOGGER.debug("Map _update: Map update with cache possible")
            try:
                self._maploop.update()
            except Exception as e:
                _LOGGER.error("Map update failed: {}.".format(e))
        else:
            _LOGGER.debug(" Map _update: No direct map update possible. Reconfiguring")
            self.last_config_change = self._configentry.modified_at
            # prevent distortion of map
            if self._height and self._width:
                width = round(self._height / 1.115)
                markers = []
                if self._configdata[CONF_MAP_HOMEMARKER]:
                    markers.append(
                        dwdmap.Marker(
                            latitude=self._hass.config.latitude,
                            longitude=self._hass.config.longitude,
                            shape=conversion_table_map_homemarker_shape[
                                self._configdata[CONF_MAP_HOMEMARKER_SHAPE]
                            ],
                            size=self._configdata[CONF_MAP_HOMEMARKER_SIZE],
                            colorRGB=tuple(self._configdata[CONF_MAP_HOMEMARKER_COLOR]),
                        )
                    )
                if self._configdata[CONF_MAP_TYPE] == CONF_MAP_TYPE_GERMANY:
                    _LOGGER.debug(
                        "map async_update get_germany map_type:{} background_type:{} width:{} height:{} steps:{} markers:{}".format(
                            self._configdata[CONF_MAP_FOREGROUND_TYPE],
                            self._configdata[CONF_MAP_BACKGROUND_TYPE],
                            width,
                            self._height,
                            self._configdata[CONF_MAP_LOOP_COUNT],
                            len(markers),
                        )
                    )
                    try:
                        maploop = dwdmap.ImageLoop(
                            dwdmap.germany_boundaries.minx,
                            dwdmap.germany_boundaries.miny,
                            dwdmap.germany_boundaries.maxx,
                            dwdmap.germany_boundaries.maxy,
                            map_types=[
                                self.map_maptype(
                                    self._configdata[CONF_MAP_FOREGROUND_TYPE]  # type: ignore
                                )
                            ],
                            background_types=[
                                self.map_maptype(
                                    self._configdata[CONF_MAP_BACKGROUND_TYPE]  # type: ignore
                                )
                            ],
                            steps=self._configdata[CONF_MAP_LOOP_COUNT],
                            image_width=width,
                            image_height=self._height,
                            markers=markers,
                            dark_mode=self._configdata[CONF_MAP_DARK_MODE],
                        )
                    except Exception as e:
                        _LOGGER.error("Map update failed: {}.".format(e))
                else:
                    _LOGGER.debug(
                        "map async_update get_from_location lat: {}, lon:{}, radius:{}, map_type:{} background_type:{} width:{} height:{} markers:{}".format(
                            self._configdata[CONF_MAP_WINDOW]["latitude"],
                            self._configdata[CONF_MAP_WINDOW]["longitude"],
                            self._configdata[CONF_MAP_WINDOW]["radius"],
                            self._configdata[CONF_MAP_FOREGROUND_TYPE],
                            self._configdata[CONF_MAP_BACKGROUND_TYPE],
                            width,
                            self._height,
                            len(markers),
                        )
                    )

                    radius = math.fabs(
                        self._configdata[CONF_MAP_WINDOW]["radius"]
                        / (
                            111.3
                            * math.cos(self._configdata[CONF_MAP_WINDOW]["latitude"])
                        )  # type: ignore
                    )
                    try:
                        maploop = dwdmap.ImageLoop(
                            self._configdata[CONF_MAP_WINDOW]["longitude"] - radius,  # type: ignore
                            self._configdata[CONF_MAP_WINDOW]["latitude"] - radius,  # type: ignore
                            self._configdata[CONF_MAP_WINDOW]["longitude"] + radius,  # type: ignore
                            self._configdata[CONF_MAP_WINDOW]["latitude"] + radius,  # type: ignore
                            map_types=[
                                self.map_maptype(
                                    self._configdata[CONF_MAP_FOREGROUND_TYPE]
                                )  # type: ignore
                            ],
                            background_types=[
                                self.map_maptype(
                                    self._configdata[CONF_MAP_BACKGROUND_TYPE]
                                )  # type: ignore
                            ],
                            steps=self._configdata[CONF_MAP_LOOP_COUNT],
                            image_width=width,
                            image_height=self._height,
                            markers=markers,
                            dark_mode=self._configdata[CONF_MAP_DARK_MODE],
                        )
                    except Exception as e:
                        _LOGGER.error("Map update failed: {}.".format(e))

                    _LOGGER.debug(
                        "map async_update maploop: {}".format(maploop.get_images())
                    )
                self._maploop = maploop
                self._cachedheight = self._height
                self._cachedwidth = self._width
            self._images = maploop.get_images()

    def _update_single(self):
        # prevent distortion of map
        if self._height and self._width:
            width = round(self._height / 1.115)
            markers = []
            if self._configdata[CONF_MAP_HOMEMARKER]:
                markers.append(
                    dwdmap.Marker(
                        latitude=self._hass.config.latitude,
                        longitude=self._hass.config.longitude,
                        shape=conversion_table_map_homemarker_shape[
                            self._configdata[CONF_MAP_HOMEMARKER_SHAPE]
                        ],
                        size=self._configdata[CONF_MAP_HOMEMARKER_SIZE],
                        colorRGB=tuple(self._configdata[CONF_MAP_HOMEMARKER_COLOR]),
                    )
                )
            if self._configdata[CONF_MAP_TYPE] == CONF_MAP_TYPE_GERMANY:
                _LOGGER.debug(
                    "map async_update get_germany map_type:{} background_type:{} width:{} height:{} markers:{}".format(
                        self._configdata[CONF_MAP_FOREGROUND_TYPE],
                        self._configdata[CONF_MAP_BACKGROUND_TYPE],
                        width,
                        self._height,
                        len(markers),
                    )
                )
                self._image = dwdmap.get_germany(
                    map_types=[
                        self.map_maptype(self._configdata[CONF_MAP_FOREGROUND_TYPE])  # type: ignore
                    ],
                    background_types=[
                        self.map_maptype(self._configdata[CONF_MAP_BACKGROUND_TYPE])  # type: ignore
                    ],
                    image_width=width,
                    image_height=self._height,
                    markers=markers,
                    dark_mode=self._configdata[CONF_MAP_DARK_MODE],
                )
            else:
                _LOGGER.debug(
                    "map async_update get_from_location lat: {}, lon:{}, radius:{}, map_type:{} background_type:{} width:{} height:{} markers:{}".format(
                        self._configdata[CONF_MAP_WINDOW]["latitude"],
                        self._configdata[CONF_MAP_WINDOW]["longitude"],
                        self._configdata[CONF_MAP_WINDOW]["radius"],
                        self._configdata[CONF_MAP_FOREGROUND_TYPE],
                        self._configdata[CONF_MAP_BACKGROUND_TYPE],
                        width,
                        self._height,
                        len(markers),
                    )
                )
                self._image = dwdmap.get_from_location(
                    latitude=self._configdata[CONF_MAP_WINDOW]["latitude"],
                    longitude=self._configdata[CONF_MAP_WINDOW]["longitude"],
                    radius_km=self._configdata[CONF_MAP_WINDOW]["radius"],
                    map_types=[
                        self.map_maptype(self._configdata[CONF_MAP_FOREGROUND_TYPE])  # type: ignore
                    ],  # type: ignore
                    background_types=[
                        self.map_maptype(self._configdata[CONF_MAP_BACKGROUND_TYPE])  # type: ignore
                    ],  # type: ignore
                    image_width=self._width,
                    image_height=self._height,
                    markers=markers,
                )

    def get_image(self):
        buf = BytesIO()
        if (
            self._configdata[CONF_MAP_FOREGROUND_TYPE]
            == CONF_MAP_FOREGROUND_PRECIPITATION
        ):
            _LOGGER.debug(
                " Map get_image: map_loop_count {}".format(
                    self._configdata[CONF_MAP_LOOP_COUNT]
                )
            )

            if self._image_nr == self._configdata[CONF_MAP_LOOP_COUNT] - 1:
                self._image_nr = 0
            else:
                self._image_nr += 1
            _LOGGER.debug(" Map get_image: _image_nr {}".format(self._image_nr))
            image = self._images[self._image_nr]  # type: ignore
        else:
            image = self._image

        if image:
            draw = PIL.ImageDraw.ImageDraw(image)
            if self._configdata[CONF_MAP_CENTERMARKER]:
                center = (image.size[0] / 2, image.size[1] / 2)
                length = 7.0
                draw.line(
                    [center[0] - length, center[1], center[0] + length, center[1]],
                    fill=(255, 0, 0),
                )
                draw.line(
                    [center[0], center[1] - length, center[0], center[1] + length],
                    fill=(255, 0, 0),
                )
            if (
                CONF_MAP_TIMESTAMP in self._configdata
                and self._configdata[CONF_MAP_TIMESTAMP]
                and self._maploop
            ):
                timestamp = self._maploop._last_update - timedelta(minutes=5) * (
                    self._configdata[CONF_MAP_LOOP_COUNT] - self._image_nr - 1
                )
                boxcolor = (0, 0, 0)
                textcolor = (255, 255, 255)
                if (
                    CONF_MAP_DARK_MODE in self._configdata
                    and self._configdata[CONF_MAP_DARK_MODE]
                ):
                    boxcolor = (225, 225, 225)
                    textcolor = (0, 0, 0)

                draw.rectangle((8, 13, 175, 32), fill=boxcolor)
                draw.text(
                    (10, 10),
                    timestamp.astimezone().strftime("%d.%m.%Y %H:%M"),
                    fill=textcolor,
                    font_size=20,
                )

            image.save(buf, format="PNG")  # type: ignore()
        return buf.getvalue()

    def map_maptype(
        self, map_type
    ) -> dwdmap.WeatherMapType | dwdmap.WeatherBackgroundMapType | None:
        if map_type == CONF_MAP_FOREGROUND_PRECIPITATION:
            return dwdmap.WeatherMapType.NIEDERSCHLAGSRADAR
        elif map_type == CONF_MAP_FOREGROUND_MAXTEMP:
            return dwdmap.WeatherMapType.MAXTEMP
        elif map_type == CONF_MAP_FOREGROUND_UVINDEX:
            return dwdmap.WeatherMapType.UVINDEX
        elif map_type == CONF_MAP_FOREGROUND_POLLENFLUG:
            return dwdmap.WeatherMapType.POLLENFLUG
        elif map_type == CONF_MAP_FOREGROUND_SATELLITE_RGB:
            return dwdmap.WeatherMapType.SATELLITE_RGB
        elif map_type == CONF_MAP_FOREGROUND_SATELLITE_IR:
            return dwdmap.WeatherMapType.SATELLITE_IR
        elif map_type == CONF_MAP_FOREGROUND_WARNUNGEN_GEMEINDEN:
            return dwdmap.WeatherMapType.WARNUNGEN_GEMEINDEN
        elif map_type == CONF_MAP_FOREGROUND_WARNUNGEN_KREISE:
            return dwdmap.WeatherMapType.WARNUNGEN_KREISE
        elif map_type == CONF_MAP_BACKGROUND_LAENDER:
            return dwdmap.WeatherBackgroundMapType.LAENDER
        elif map_type == CONF_MAP_BACKGROUND_BUNDESLAENDER:
            return dwdmap.WeatherBackgroundMapType.BUNDESLAENDER
        elif map_type == CONF_MAP_BACKGROUND_KREISE:
            return dwdmap.WeatherBackgroundMapType.KREISE
        elif map_type == CONF_MAP_BACKGROUND_GEMEINDEN:
            return dwdmap.WeatherBackgroundMapType.GEMEINDEN
        elif map_type == CONF_MAP_BACKGROUND_SATELLIT:
            return dwdmap.WeatherBackgroundMapType.SATELLIT

    def set_size(
        self,
        image_width,
        image_height,
    ):
        if image_width > 1200:
            image_width = 1200
        if image_height > 1400:
            image_height = 1400
        self._width = image_width
        self._height = image_height
