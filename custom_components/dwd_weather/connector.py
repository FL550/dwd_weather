"""Connector class to retrieve data, which is use by the weather and sensor enities."""

import logging
from datetime import datetime, timedelta, timezone
import math
import re
import time
import PIL
import PIL.ImageDraw
from markdownify import markdownify
from homeassistant.config_entries import ConfigEntry
from homeassistant.util import dt
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
from simple_dwd_weatherforecast.dwdairquality import (
    AirQuality,
)

from .const import (
    ATTR_FORECAST_APPARENT_TEMP,
    ATTR_FORECAST_AIRQUALITY_OZON,
    ATTR_FORECAST_AIRQUALITY_PM10,
    ATTR_FORECAST_AIRQUALITY_PM2_5,
    ATTR_FORECAST_AIRQUALITY_STICKSTOFFDIOXID,
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
    CONF_DOWNLOAD_AIRQUALITY,
    CONF_DOWNLOAD_APPARENT_TEMPERATURE,
    CONF_DOWNLOAD_PRECIPITATION_SENSORS,
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
        self._report = None
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

        self._forecast_daily_cache = None
        self._forecast_daily_cache_update = None
        self._forecast_daily_cache_day = None
        self._forecast_hourly_cache = None
        self._forecast_hourly_cache_update = None
        self._forecast_hourly_cache_hour = None
        self._forecast_timestamp_cache = {}
        self._forecast_timestamp_cache_update = None

        self._airquality_station_id = None
        self._airquality_hourly = None
        self._airquality_daily = None
        self._radar_precipitation_forecast = None
        self._radar_next_precipitation = None

    def register_entity(self, entity):
        self.entities.append(entity)

    def supports_apparent_temperature(self) -> bool:
        """Return whether apparent temperature data can be requested."""
        if not self._config.get(CONF_DOWNLOAD_APPARENT_TEMPERATURE, False):
            return False

        supports_fn = getattr(self.dwd_weather, "supports_apparent_temperature", None)
        if callable(supports_fn):
            return bool(supports_fn())

        return True

    async def async_update(self):
        """Async wrapper for update method."""
        if (
            self._config.get(CONF_DOWNLOAD_AIRQUALITY, False)
            and self.dwd_weather.station
            and self._airquality_hourly is None
            and self._airquality_daily is None
        ):
            try:
                self._airquality_hourly = await AirQuality.get_station_from_location(
                    self.dwd_weather.station["lat"],
                    self.dwd_weather.station["lon"],
                    "hourly",
                )
                self._airquality_station_id = self._airquality_hourly.station_id
                if self._airquality_station_id is not None:
                    self._airquality_daily = await AirQuality.create(
                        self._airquality_station_id,
                        "daily",
                    )
            except Exception as error:
                _LOGGER.warning("Failed to initialize air quality data: %s", error)
        if await self._hass.async_add_executor_job(self._update):
            for entity in self.entities:
                await entity.async_update_listeners(("daily", "hourly"))

    def _update(self):
        """Get the latest data from DWD."""
        timestamp = datetime.now(timezone.utc)
        if timestamp.minute % 10 != 0 and self.latest_update is not None:
            return False

        _LOGGER.info("Updating {}".format(self._config[CONF_STATION_NAME]))
        current_hour_data = None
        if self._config[CONF_HOURLY_UPDATE]:
            if self.dwd_weather.forecast_data and self.dwd_weather.is_in_timerange(
                timestamp
            ):
                current_hour_data = self.dwd_weather.forecast_data[  # type: ignore
                    self.dwd_weather.strip_to_hour_str(timestamp)
                ]

        should_request_measurements = self._config[CONF_DATA_TYPE] in (
            CONF_DATA_TYPE_REPORT,
            CONF_DATA_TYPE_MIXED,
        )
        self.dwd_weather.update(
            force_hourly=self._config[CONF_HOURLY_UPDATE],
            with_forecast=True,
            with_measurements=should_request_measurements,
            with_report=True,
            with_uv=True,
            with_apparent_temperature=self.supports_apparent_temperature(),
        )

        self._update_radar_precipitation()

        if self._config.get(CONF_DOWNLOAD_AIRQUALITY, False):
            if self._airquality_hourly is not None:
                self._airquality_hourly.update()
            if self._airquality_daily is not None:
                self._airquality_daily.update(with_current_day=True)

        if self._config[CONF_HOURLY_UPDATE] and not self.dwd_weather.is_in_timerange(
            timestamp
        ):
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
                missing_hour_key = (first_date - timedelta(hours=1)).strftime(
                    "%Y-%m-%dT%H:00:00.000Z"
                )
                self.dwd_weather.forecast_data[missing_hour_key] = current_hour_data
                self.dwd_weather.forecast_data.move_to_end(
                    missing_hour_key,
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
            date = f"20{report_date_array[2]}-{report_date_array[1]}-{report_date_array[0]}T{self.dwd_weather.report_data['time']}:00+00:00"
            self.infos[ATTR_REPORT_ISSUE_TIME] = date
        else:
            self.infos[ATTR_REPORT_ISSUE_TIME] = ""
        self.infos[ATTR_ISSUE_TIME] = self.dwd_weather.issue_time
        self.infos[ATTR_STATION_ID] = self._config[CONF_STATION_ID]
        self.infos[ATTR_STATION_NAME] = self._config[CONF_STATION_NAME]

        weather_report_text = self.dwd_weather.get_weather_report(shouldUpdate=False)
        report_text = (
            markdownify(weather_report_text, strip=["pre", "br"])
            if weather_report_text is not None
            else None
        )
        match = (
            re.search(
                r"\w+, \d{2}\.\d{2}\.\d{2}, \d{2}:\d{2}",
                report_text,
            )
            if report_text is not None
            else None
        )
        self._report = {
            "text": report_text,
            "time": match.group() if match is not None else None,
        }

        _LOGGER.debug("Forecast data {}".format(self.dwd_weather.forecast_data))
        return True

    def _update_radar_precipitation(self) -> None:
        """Refresh radar precipitation data during connector update cycle only."""
        self._radar_precipitation_forecast = None
        self._radar_next_precipitation = None

        if not self._config.get(CONF_DOWNLOAD_PRECIPITATION_SENSORS, False):
            return

        try:
            self._radar_precipitation_forecast = (
                self.dwd_weather.get_radar_precipitation_forecast(shouldUpdate=True)
            )
        except Exception as error:
            _LOGGER.warning("Failed to update radar precipitation forecast: %s", error)

        try:
            # Reuse freshly downloaded data from forecast call where possible.
            self._radar_next_precipitation = (
                self.dwd_weather.get_radar_next_precipitation(shouldUpdate=False)
            )
        except Exception as error:
            _LOGGER.warning(
                "Failed to update radar next precipitation details: %s", error
            )

    def get_forecast(
        self, forecast_feature: WeatherEntityFeature
    ) -> list[Forecast] | None:
        forecast_getters = {
            WeatherEntityFeature.FORECAST_HOURLY: self.get_forecast_hourly,
            WeatherEntityFeature.FORECAST_DAILY: self.get_forecast_daily,
        }
        getter = forecast_getters.get(forecast_feature)
        return getter() if getter is not None else None

    def _should_add_airquality_to_forecast(self) -> bool:
        return self._config.get(
            CONF_ADDITIONAL_FORECAST_ATTRIBUTES, False
        ) and self._config.get(CONF_DOWNLOAD_AIRQUALITY, False)

    @staticmethod
    def _to_forecast_airquality_fields(airquality_entry: dict | None) -> dict:
        if not isinstance(airquality_entry, dict):
            return {}

        # Keep key names aligned with dedicated air quality sensors.
        mapping = {
            "Stickstoffdioxid": ATTR_FORECAST_AIRQUALITY_STICKSTOFFDIOXID,
            "Ozon": ATTR_FORECAST_AIRQUALITY_OZON,
            "PM2_5": ATTR_FORECAST_AIRQUALITY_PM2_5,
            "PM10": ATTR_FORECAST_AIRQUALITY_PM10,
        }
        result = {}
        for source_key, target_key in mapping.items():
            if source_key in airquality_entry:
                result[target_key] = airquality_entry[source_key]
        return result

    def _get_airquality_forecast_values(
        self, forecast_type: WeatherEntityFeature, index: int
    ) -> dict:
        if not self._should_add_airquality_to_forecast():
            return {}

        airquality_data = self._resolve_airquality_source(forecast_type)
        if forecast_type == WeatherEntityFeature.FORECAST_HOURLY:
            if isinstance(airquality_data, list) and index < len(airquality_data):
                return self._to_forecast_airquality_fields(airquality_data[index])
            return {}

        if isinstance(airquality_data, dict):
            day_keys = ["today", "tomorrow", "day_after"]
            if index < len(day_keys):
                return self._to_forecast_airquality_fields(
                    airquality_data.get(day_keys[index])
                )
            return {}

        if isinstance(airquality_data, list) and index < len(airquality_data):
            return self._to_forecast_airquality_fields(airquality_data[index])

        return {}

    def get_forecast_hourly(self) -> list[Forecast] | None:
        start_time = time.perf_counter()
        weather_interval = 1
        # now = dt.now()
        now = datetime.now(timezone.utc)
        current_hour = now.replace(minute=0, second=0, microsecond=0)
        # Check if cache is valid
        if (
            self._forecast_hourly_cache is not None
            and self._forecast_hourly_cache_update == self.latest_update
            and self._forecast_hourly_cache_hour == current_hour
        ):
            _LOGGER.debug("Hourly forecast cache hit")
            end_time = time.perf_counter()
            _LOGGER.info(
                f"get_forecast_hourly (cached) executed in {end_time - start_time:.4f} seconds"
            )
            return self._forecast_hourly_cache

        forecast_data = []
        if self.latest_update and self.dwd_weather.is_in_timerange(now):
            timestep = datetime(
                now.year,
                now.month,
                now.day,
                now.hour,
                tzinfo=timezone.utc,
            )

            forecast_index = 0
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

                    if self.supports_apparent_temperature():
                        apparent_temp = self.dwd_weather.get_apparent_temperature(
                            shouldUpdate=False
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
                    if self.supports_apparent_temperature():
                        data_item[ATTR_FORECAST_APPARENT_TEMP] = (
                            round(apparent_temp - 273.1, 1)
                            if apparent_temp is not None
                            else None
                        )
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
                        if (
                            self._config[CONF_DOWNLOAD_AIRQUALITY]
                            and self._airquality_hourly is not None
                        ):
                            data_item.update(
                                self._get_airquality_forecast_values(
                                    WeatherEntityFeature.FORECAST_HOURLY,
                                    forecast_index,
                                )
                            )
                    forecast_data.append(data_item)
                    forecast_index += 1
                    timestep += timedelta(hours=weather_interval)
        end_time = time.perf_counter()
        _LOGGER.info(
            f"get_forecast_hourly executed in {end_time - start_time:.4f} seconds"
        )
        # Update cache
        self._forecast_hourly_cache = forecast_data
        self._forecast_hourly_cache_update = self.latest_update
        self._forecast_hourly_cache_hour = current_hour
        return forecast_data

    def get_forecast_daily(self) -> list[Forecast] | None:
        start_time = time.perf_counter()
        weather_interval = 24
        now = dt.now()
        # Check if cache is valid
        current_day = now.date()
        if (
            self._forecast_daily_cache is not None
            and self._forecast_daily_cache_update == self.latest_update
            and self._forecast_daily_cache_day == current_day
        ):
            _LOGGER.debug("Daily forecast cache hit")
            end_time = time.perf_counter()
            _LOGGER.info(
                f"get_forecast_daily (cached) executed in {end_time - start_time:.4f} seconds"
            )
            return self._forecast_daily_cache

        forecast_data = []
        if self.latest_update and self.dwd_weather.is_in_timerange(now):
            timestep = datetime(
                now.year,
                now.month,
                now.day,
                tzinfo=now.tzinfo,
            )

            for day_index in range(0, 9):
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
                    data_item.update(
                        self._get_airquality_forecast_values(
                            WeatherEntityFeature.FORECAST_DAILY,
                            day_index,
                        )
                    )
                forecast_data.append(data_item)
                timestep += timedelta(hours=weather_interval)
        _LOGGER.debug("Daily Forecast data {}".format(forecast_data))
        end_time = time.perf_counter()
        _LOGGER.info(
            f"get_forecast_daily executed in {end_time - start_time:.4f} seconds"
        )
        # Update cache
        self._forecast_daily_cache = forecast_data
        self._forecast_daily_cache_update = self.latest_update
        self._forecast_daily_cache_day = current_day
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
        return self._report["text"] if self._report else None

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
            if not hasattr(self, "_interpolate_value"):
                self._interpolate_value = {}
            now_time_actual = datetime.now(timezone.utc)
            if data_type not in self._interpolate_value:
                self._interpolate_value[data_type] = (value, now_time_actual)
            next_value = self.dwd_weather.get_forecast_data(
                data_type,
                now_time_actual + timedelta(hours=1),
                shouldUpdate=False,
            )
            if next_value is not None:
                next_hour_time = self.dwd_weather.strip_to_hour(
                    now_time_actual
                ).replace(tzinfo=timezone.utc) + timedelta(hours=1)
                value_diff = round(
                    next_value - self._interpolate_value[data_type][0], 2
                )
                total_time_diff = (
                    next_hour_time - self._interpolate_value[data_type][1]
                ).seconds
                elapsed_time_diff = (
                    now_time_actual - self._interpolate_value[data_type][1]
                ).seconds
                if total_time_diff != 0:
                    new_value = round(
                        self._interpolate_value[data_type][0]
                        + (value_diff * (elapsed_time_diff / total_time_diff)),
                        2,
                    )
                else:
                    new_value = self._interpolate_value[data_type][0]

                self._interpolate_value[data_type] = (new_value, now_time_actual)
                value = new_value

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

    def get_apparent_temperature(self):
        if not self.supports_apparent_temperature():
            return None

        apparent_temp = self.dwd_weather.get_apparent_temperature(shouldUpdate=False)
        return apparent_temp - 273.15 if apparent_temp is not None else None

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

    def get_radar_precipitation_now(self):
        forecast = self._radar_precipitation_forecast
        if not isinstance(forecast, dict) or len(forecast) == 0:
            return None

        now_ts = datetime.now(timezone.utc)
        items = sorted(forecast.items())
        current = None
        for timestamp, value in items:
            if timestamp <= now_ts:
                current = value
            elif current is not None:
                break

        if current is None:
            current = items[0][1]
        return round(current, 1) if current is not None else None

    def get_radar_next_precipitation_start(self):
        if not isinstance(self._radar_next_precipitation, dict):
            return None
        start = self._radar_next_precipitation.get("start")
        if start is None:
            return None
        return start.strftime("%Y-%m-%dT%H:%M:%S+00:00")

    def get_radar_next_precipitation_attributes(self):
        if not isinstance(self._radar_next_precipitation, dict):
            return {}
        result = {}
        end = self._radar_next_precipitation.get("end")
        if end is not None:
            result["end"] = end.strftime("%Y-%m-%dT%H:%M:%S+00:00")
        length = self._radar_next_precipitation.get("length")
        if length is not None:
            result["length"] = int(length.total_seconds() / 60)
        max_val = self._radar_next_precipitation.get("max")
        if max_val is not None:
            result["max"] = round(max_val, 1)
        sum_val = self._radar_next_precipitation.get("sum")
        if sum_val is not None:
            result["sum"] = round(sum_val, 1)
        return result

    def get_radar_precipitation_hourly(self):
        forecast = self._radar_precipitation_forecast
        if not isinstance(forecast, dict):
            return []

        result = []
        for timestamp, value in sorted(forecast.items()):
            result.append(
                {
                    ATTR_FORECAST_TIME: timestamp.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "value": round(value, 1) if value is not None else None,
                }
            )

        if self._config[CONF_SENSOR_FORECAST_STEPS]:
            return result[: self._config[CONF_SENSOR_FORECAST_STEPS]]
        return result

    def _resolve_airquality_source(
        self, forecast_type: WeatherEntityFeature
    ) -> dict | list | None:
        if not self._config.get(CONF_DOWNLOAD_AIRQUALITY, False):
            return None

        # Fallback to dedicated airquality download objects.
        source = (
            self._airquality_daily
            if forecast_type == WeatherEntityFeature.FORECAST_DAILY
            else self._airquality_hourly
        )
        if source is not None:
            return source.data

        return None

    def get_airquality(
        self, forecast_type: WeatherEntityFeature = WeatherEntityFeature.FORECAST_HOURLY
    ):
        data = self._resolve_airquality_source(forecast_type)
        if data is None:
            return None

        if forecast_type == WeatherEntityFeature.FORECAST_DAILY:
            if isinstance(data, dict):
                return data.get("today", data)
            if isinstance(data, list) and len(data) > 0:
                return data[0]
            return None

        if isinstance(data, list):
            return data[0] if len(data) > 0 else None
        return data

    def get_airquality_hourly(self):
        data = self._resolve_airquality_source(WeatherEntityFeature.FORECAST_HOURLY)
        if not isinstance(data, list) or len(data) == 0:
            return []

        timestamp = datetime.now(timezone.utc).replace(
            minute=0, second=0, microsecond=0
        )
        result = []
        for index, item in enumerate(data):
            if (
                self._config[CONF_SENSOR_FORECAST_STEPS]
                and index >= self._config[CONF_SENSOR_FORECAST_STEPS]
            ):
                break
            result.append(
                {
                    ATTR_FORECAST_TIME: (timestamp + timedelta(hours=index)).strftime(
                        "%Y-%m-%dT%H:00:00Z"
                    ),
                    "value": item,
                }
            )
        return result

    def get_airquality_daily(self):
        data = self._resolve_airquality_source(WeatherEntityFeature.FORECAST_DAILY)
        if isinstance(data, dict):
            return data
        if isinstance(data, list) and len(data) > 0:
            result = {"today": data[0]}
            if len(data) > 1:
                result["tomorrow"] = data[1]
            if len(data) > 2:
                result["day_after"] = data[2]
            return result
        return None

    def get_airquality_state(self):
        current = self.get_airquality(WeatherEntityFeature.FORECAST_HOURLY)
        if current is None:
            return None
        # Prefer PM2.5 as the sensor state and expose full pollutant data in attributes.
        return current.get("PM2_5")

    def get_airquality_component_state(self, component_name: str):
        current = self.get_airquality(WeatherEntityFeature.FORECAST_HOURLY)
        if not isinstance(current, dict):
            return None
        return current.get(component_name)

    def get_airquality_component_hourly(self, component_name: str):
        data = self.get_airquality_hourly()
        result = []
        for item in data:
            value = item.get("value")
            if isinstance(value, dict):
                result.append(
                    {
                        ATTR_FORECAST_TIME: item.get(ATTR_FORECAST_TIME),
                        "value": value.get(component_name),
                    }
                )
        return result

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

    def _get_forecast_timestamp(self, key: str) -> datetime:
        if self._forecast_timestamp_cache_update != self.latest_update:
            self._forecast_timestamp_cache = {}
            self._forecast_timestamp_cache_update = self.latest_update

        timestamp = self._forecast_timestamp_cache.get(key)
        if timestamp is None:
            timestamp = datetime(
                *(time.strptime(key, "%Y-%m-%dT%H:%M:%S.%fZ")[0:6]),
                0,
                timezone.utc,
            )
            self._forecast_timestamp_cache[key] = timestamp
        return timestamp

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
                if self._get_forecast_timestamp(key) < timestamp:
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

    def get_apparent_temperature_hourly(self):
        if not self.supports_apparent_temperature():
            return []

        data = []
        forecast_data = self.dwd_weather.get_apparent_temperature_forecast(
            shouldUpdate=False
        )
        if forecast_data:
            for key in forecast_data:
                value = forecast_data[key]
                if value is not None:
                    value = round(value - 273.15, 1)
                data.append({ATTR_FORECAST_TIME: key, "value": value})
        return data

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
                _LOGGER.error("Map update from cache failed: {}.".format(e))
                self._maploop = None  # Invalidate cache so next call will reconfigure
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
                        self._maploop = dwdmap.ImageLoop(
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
                        _LOGGER.error("Map update germany failed: {}.".format(e))
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
                        self._maploop = dwdmap.ImageLoop(
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
                    if self._maploop:
                        _LOGGER.debug(
                            "map async_update maploop: {}".format(
                                self._maploop.get_images()
                            )
                        )
                self._cachedheight = self._height
                self._cachedwidth = self._width
            if self._maploop:
                self._images = self._maploop.get_images()

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
        image = None
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
            if self._images:
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
