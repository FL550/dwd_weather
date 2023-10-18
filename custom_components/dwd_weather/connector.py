"""Connector class to retrieve data, which is use by the weather and sensor enities."""
import logging
from datetime import datetime, timedelta, timezone
import time
from markdownify import markdownify
from homeassistant.config_entries import ConfigEntry

from homeassistant.components.weather import (
    ATTR_FORECAST_CONDITION,
    ATTR_FORECAST_NATIVE_PRECIPITATION,
    ATTR_FORECAST_NATIVE_TEMP,
    ATTR_FORECAST_NATIVE_TEMP_LOW,
    ATTR_FORECAST_TIME,
    ATTR_FORECAST_WIND_BEARING,
    ATTR_FORECAST_NATIVE_WIND_SPEED,
    WeatherEntityFeature,
    Forecast,
)
from simple_dwd_weatherforecast import dwdforecast
from simple_dwd_weatherforecast.dwdforecast import WeatherDataType

from .const import (
    ATTR_ISSUE_TIME,
    ATTR_REPORT_ISSUE_TIME,
    ATTR_LATEST_UPDATE,
    ATTR_STATION_ID,
    ATTR_STATION_NAME,
    CONF_DATA_TYPE,
    CONF_DATA_TYPE_FORECAST,
    CONF_DATA_TYPE_MIXED,
    CONF_DATA_TYPE_REPORT,
    CONF_INTERPOLATE,
    CONF_STATION_ID,
    CONF_STATION_NAME,
    CONF_WIND_DIRECTION_TYPE,
    CONF_HOURLY_UPDATE,
    DEFAULT_WIND_DIRECTION_TYPE,
)

_LOGGER = logging.getLogger(__name__)


class DWDWeatherData:
    def __init__(self, hass, config_entry: ConfigEntry):
        """Initialize the data object."""
        self._config = config_entry.data
        self._hass = hass
        self.forecast = None
        self.latest_update = None
        self.infos = {}

        # Holds the current data from DWD
        self.dwd_weather = dwdforecast.Weather(self._config[CONF_STATION_ID])

    async def async_update(self):
        """Async wrapper for update method."""
        return await self._hass.async_add_executor_job(self._update)

    def _update(self):
        """Get the latest data from DWD."""
        timestamp = datetime.now(timezone.utc)
        if timestamp.minute % 10 == 0 or self.latest_update is None:
            _LOGGER.info("Updating {}".format(self._config[CONF_STATION_NAME]))
            self.dwd_weather.update(
                force_hourly=self._config[CONF_HOURLY_UPDATE],
                with_forecast=True,
                with_measurements=True
                if self._config[CONF_DATA_TYPE] == CONF_DATA_TYPE_REPORT
                or self._config[CONF_DATA_TYPE] == CONF_DATA_TYPE_MIXED
                else False,
                with_report=True,
            )
            if self._config[CONF_HOURLY_UPDATE]:
                # Hacky workaround: as the hourly data does not provide a forecast for the actual hour, we have to clone the next hour and pretend we have a forecast
                first_date = datetime(
                    *(
                        time.strptime(
                            next(iter(self.dwd_weather.forecast_data)),
                            "%Y-%m-%dT%H:%M:%S.%fZ",
                        )[0:6]
                    ),
                    0,
                    timezone.utc,
                )
                self.dwd_weather.forecast_data[
                    (first_date - timedelta(hours=1)).strftime("%Y-%m-%dT%H:00:00.000Z")
                ] = self.dwd_weather.forecast_data[
                    first_date.strftime("%Y-%m-%dT%H:00:00.000Z")
                ]
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

    def get_forecast(self, WeatherEntityFeature_FORECAST) -> list[Forecast] | None:
        if WeatherEntityFeature_FORECAST == WeatherEntityFeature.FORECAST_HOURLY:
            weather_interval = 1
        elif WeatherEntityFeature_FORECAST == WeatherEntityFeature.FORECAST_DAILY:
            weather_interval = 24
        timestep = datetime(
            self.latest_update.year,
            self.latest_update.month,
            self.latest_update.day,
            tzinfo=timezone.utc,
        )
        forecast_data = []
        # Find the next timewindow from actual time
        while timestep < self.latest_update:
            timestep += timedelta(hours=weather_interval)
            # Reduce by one to include the current timewindow
        timestep -= timedelta(hours=weather_interval)
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
                    and (timestep.hour < 6 or timestep.hour > 21)
                ):
                    condition = "clear-night"
                temp_max = self.dwd_weather.get_timeframe_max(
                    WeatherDataType.TEMPERATURE,
                    timestep,
                    weather_interval,
                    False,
                )
                if temp_max is not None:
                    temp_max = int(round(temp_max - 273.1, 0))

                temp_min = self.dwd_weather.get_timeframe_min(
                    WeatherDataType.TEMPERATURE,
                    timestep,
                    weather_interval,
                    False,
                )
                if temp_min is not None:
                    temp_min = int(round(temp_min - 273.1, 0))

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
                data_item = {
                    ATTR_FORECAST_TIME: timestep.strftime("%Y-%m-%dT%H:00:00Z"),
                    ATTR_FORECAST_CONDITION: condition,
                    ATTR_FORECAST_NATIVE_TEMP: temp_max,
                    ATTR_FORECAST_NATIVE_PRECIPITATION: self.dwd_weather.get_timeframe_sum(
                        WeatherDataType.PRECIPITATION,
                        timestep,
                        weather_interval,
                        False,
                    ),
                    ATTR_FORECAST_WIND_BEARING: wind_dir,
                    ATTR_FORECAST_NATIVE_WIND_SPEED: self.dwd_weather.get_timeframe_max(
                        WeatherDataType.WIND_SPEED,
                        timestep,
                        weather_interval,
                        False,
                    ),
                    "wind_gusts": self.dwd_weather.get_timeframe_max(
                        WeatherDataType.WIND_GUSTS,
                        timestep,
                        weather_interval,
                        False,
                    ),
                    "precipitation_probability": precipitation_prop,
                }
                if weather_interval == 24:
                    data_item[ATTR_FORECAST_NATIVE_TEMP_LOW] = temp_min
                forecast_data.append(data_item)
                timestep += timedelta(hours=weather_interval)
        return forecast_data

    def get_condition(self):
        now = datetime.now(timezone.utc)
        condition = self.dwd_weather.get_forecast_condition(now, False)
        if condition == "sunny" and (now.hour < 6 or now.hour > 21):
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
            value = self.dwd_weather.get_reported_weather(
                data_type,
                shouldUpdate=False,
            )
        if conf_data_type == CONF_DATA_TYPE_FORECAST or (
            conf_data_type == CONF_DATA_TYPE_MIXED and value is None
        ):
            value = self.dwd_weather.get_forecast_data(
                data_type,
                datetime.now(timezone.utc),
                shouldUpdate=False,
            )

        if self._config[CONF_INTERPOLATE]:
            now_time_actual = datetime.now(timezone.utc)
            next_value = self.dwd_weather.get_forecast_data(
                data_type,
                now_time_actual + timedelta(hours=1),
                shouldUpdate=False,
            )
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
            WeatherDataType.WIND_DIRECTION: lambda x: round(x, 0)
            if self._config[CONF_WIND_DIRECTION_TYPE] == DEFAULT_WIND_DIRECTION_TYPE
            else self.get_wind_direction_symbol(round(x, 0)),
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

    def get_condition_hourly(self):
        data = []
        forecast_data = self.dwd_weather.forecast_data
        for key in forecast_data:
            item = forecast_data[key][WeatherDataType.CONDITION.value[0]]
            value = self.dwd_weather.weather_codes[item][0] if item != "-" else None
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
            WeatherDataType.WIND_DIRECTION: lambda value: round(value, 0)
            if self._config[CONF_WIND_DIRECTION_TYPE] == DEFAULT_WIND_DIRECTION_TYPE
            else self.get_wind_direction_symbol(round(value, 0)),
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

        for key in forecast_data:
            if (
                datetime(
                    *(time.strptime(key, "%Y-%m-%dT%H:%M:%S.%fZ")[0:6]), 0, timezone.utc
                )
                < timestamp
            ):
                continue

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

    def get_wind_direction_symbol(self, value):
        if value < 22.5:
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
