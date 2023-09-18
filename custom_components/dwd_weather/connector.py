"""Connector class to retrieve data, which is use by the weather and sensor enities."""
import logging
from datetime import datetime, timedelta, timezone
import time
from markdownify import markdownify
from homeassistant.config_entries import ConfigEntry

from homeassistant.components.weather import (
    ATTR_FORECAST_CONDITION,
    ATTR_FORECAST_NATIVE_PRECIPITATION,
    ATTR_FORECAST_NATIVE_PRESSURE,
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
    CONF_STATION_ID,
    CONF_STATION_NAME,
    CONF_WIND_DIRECTION_TYPE,
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
        """Get the latest data from DWD and generate forecast array."""
        timestamp = datetime.now(timezone.utc)
        # Only update on the hour and when not updated yet
        # TODO and report if new is available, vielleicht alle 10 MInuten?
        if timestamp.minute == 0 or self.latest_update is None:
            self.dwd_weather.update(
                force_hourly=False,
                with_forecast=True,
                with_measurements=True
                if self._config[CONF_DATA_TYPE] == "report_data"
                else False,
                with_report=True,
            )
            _LOGGER.info("Updating {}".format(self._config[CONF_STATION_NAME]))
            self.infos[ATTR_LATEST_UPDATE] = timestamp
            self.latest_update = timestamp

            self.infos[ATTR_REPORT_ISSUE_TIME] = (
                f"{self.dwd_weather.report_data['date']} {self.dwd_weather.report_data['time']}"
                if self._config[CONF_DATA_TYPE] == "report_data"
                else ""
            )
            self.infos[ATTR_ISSUE_TIME] = self.dwd_weather.issue_time
            self.infos[ATTR_STATION_ID] = self._config[CONF_STATION_ID]
            self.infos[ATTR_STATION_NAME] = self._config[CONF_STATION_NAME]

            _LOGGER.debug("infos '{}'".format(self.infos))

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
                forecast_data.append(
                    {
                        ATTR_FORECAST_TIME: timestep.strftime("%Y-%m-%dT%H:00:00Z"),
                        ATTR_FORECAST_CONDITION: self.dwd_weather.get_timeframe_condition(
                            timestep,
                            weather_interval,
                            False,
                        ),
                        ATTR_FORECAST_NATIVE_TEMP: temp_max,
                        ATTR_FORECAST_NATIVE_TEMP_LOW: temp_min,
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
                )
                timestep += timedelta(hours=weather_interval)
        return forecast_data

    def get_condition(self):
        return self.dwd_weather.get_forecast_condition(
            datetime.now(timezone.utc), False
        )

    def get_weather_report(self):
        return markdownify(self.dwd_weather.get_weather_report(), strip=["br"])

    def get_weather_value(self, data_type: WeatherDataType):
        if self._config[CONF_DATA_TYPE] == "report_data":
            value = self.dwd_weather.get_reported_weather(
                data_type,
                shouldUpdate=False,
            )
        else:
            value = self.dwd_weather.get_forecast_data(
                data_type,
                datetime.now(timezone.utc),
                shouldUpdate=False,
            )
        if value is not None:
            if data_type == WeatherDataType.TEMPERATURE:
                value = round(value - 273.1, 1)
            elif data_type == WeatherDataType.DEWPOINT:
                value = round(value - 273.1, 1)
            elif data_type == WeatherDataType.PRESSURE:
                value = round(value / 100, 1)
            elif data_type == WeatherDataType.WIND_SPEED:
                value = round(value * 3.6, 1)
            elif data_type == WeatherDataType.WIND_DIRECTION:
                if (
                    self._config[CONF_WIND_DIRECTION_TYPE]
                    == DEFAULT_WIND_DIRECTION_TYPE
                ):
                    value = round(value, 0)
                else:
                    value = self.get_wind_direction_symbol(round(value, 0))
            elif data_type == WeatherDataType.WIND_GUSTS:
                value = round(value * 3.6, 1)
            elif data_type == WeatherDataType.PRECIPITATION:
                value = round(value, 1)
            elif data_type == WeatherDataType.PRECIPITATION_PROBABILITY:
                value = round(value, 0)
            elif data_type == WeatherDataType.PRECIPITATION_DURATION:
                value = round(value, 1)
            elif data_type == WeatherDataType.CLOUD_COVERAGE:
                value = round(value, 0)
            elif data_type == WeatherDataType.VISIBILITY:
                value = round(value / 1000, 1)
            elif data_type == WeatherDataType.SUN_DURATION:
                value = round(value, 0)
            elif data_type == WeatherDataType.SUN_IRRADIANCE:
                value = round(value / 3.6, 0)
            elif data_type == WeatherDataType.FOG_PROBABILITY:
                value = round(value, 0)
            elif data_type == WeatherDataType.HUMIDITY:
                value = round(value, 1)

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
            if item != "-":
                value = self.dwd_weather.weather_codes[item][0]
            else:
                value = None
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
        for key in forecast_data:
            if (
                datetime(
                    *(time.strptime(key, "%Y-%m-%dT%H:%M:%S.%fZ")[0:6]),
                    0,
                    timezone.utc,
                )
                < timestamp
            ):
                continue

            item = forecast_data[key]
            value = item[data_type.value[0]]
            if value is not None:
                if data_type == WeatherDataType.TEMPERATURE:
                    value = round(value - 273.1, 1)
                elif data_type == WeatherDataType.DEWPOINT:
                    value = round(value - 273.1, 1)
                elif data_type == WeatherDataType.PRESSURE:
                    value = round(value / 100, 1)
                elif data_type == WeatherDataType.WIND_SPEED:
                    value = round(value * 3.6, 1)
                elif data_type == WeatherDataType.WIND_DIRECTION:
                    if (
                        self._config[CONF_WIND_DIRECTION_TYPE]
                        == DEFAULT_WIND_DIRECTION_TYPE
                    ):
                        value = round(value, 0)
                    else:
                        value = self.get_wind_direction_symbol(round(value, 0))
                elif data_type == WeatherDataType.WIND_GUSTS:
                    value = round(value * 3.6, 1)
                elif data_type == WeatherDataType.PRECIPITATION:
                    value = round(value, 1)
                elif data_type == WeatherDataType.PRECIPITATION_PROBABILITY:
                    value = round(value, 0)
                elif data_type == WeatherDataType.PRECIPITATION_DURATION:
                    value = round(value, 1)
                elif data_type == WeatherDataType.CLOUD_COVERAGE:
                    value = round(value, 0)
                elif data_type == WeatherDataType.VISIBILITY:
                    value = round(value / 1000, 1)
                elif data_type == WeatherDataType.SUN_DURATION:
                    value = round(value, 0)
                elif data_type == WeatherDataType.SUN_IRRADIANCE:
                    value = round(value / 3.6, 0)
                elif data_type == WeatherDataType.FOG_PROBABILITY:
                    value = round(value, 0)
                elif data_type == WeatherDataType.HUMIDITY:
                    value = round(value, 1)
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
