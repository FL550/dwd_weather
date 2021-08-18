"""Connector class to retrieve data, which is use by the weather and sensor enities."""
import logging
from datetime import datetime, timedelta, timezone
import time
from markdownify import markdownify

from homeassistant.components.weather import (
    ATTR_FORECAST_CONDITION,
    ATTR_FORECAST_PRECIPITATION,
    ATTR_FORECAST_TEMP,
    ATTR_FORECAST_TEMP_LOW,
    ATTR_FORECAST_TIME,
)
from simple_dwd_weatherforecast import dwdforecast
from simple_dwd_weatherforecast.dwdforecast import WeatherDataType

from .const import (
    ATTR_ISSUE_TIME,
    ATTR_LATEST_UPDATE,
    ATTR_STATION_ID,
    ATTR_STATION_NAME,
)

_LOGGER = logging.getLogger(__name__)


class DWDWeatherData:
    def __init__(self, hass, latitude, longitude, station_id, weather_interval):
        """Initialize the data object."""
        self._hass = hass
        self.forecast = None
        self.station_id = None
        self.latest_update = None

        # Public attributes
        self.latitude = latitude
        self.longitude = longitude
        self.weather_interval = weather_interval
        self.infos = {}

        # Checks if station_id was set by the user
        if station_id != "":
            if dwdforecast.is_valid_station_id(station_id):
                self.station_id = station_id
            else:
                raise ValueError("Not a valid station_id")
        else:
            self.station_id = dwdforecast.get_nearest_station_id(latitude, longitude)
        # Holds the current data from DWD
        self.dwd_weather = dwdforecast.Weather(self.station_id)

    async def async_update(self):
        """Async wrapper for update method."""
        return await self._hass.async_add_executor_job(self._update)

    def _update(self):
        """Get the latest data from DWD and generate forecast array."""
        timestamp = datetime.now(timezone.utc)
        # Only update on the hour and when not updated yet
        if timestamp.minute == 0 or self.latest_update is None:
            self.dwd_weather.update()
            if self.dwd_weather.get_station_name(False) == "":
                _LOGGER.exception("No update possible")
            else:
                _LOGGER.info(
                    "Updating {}".format(self.dwd_weather.get_station_name(False))
                )
                self.infos[ATTR_LATEST_UPDATE] = timestamp
                self.latest_update = timestamp
                self.infos[ATTR_ISSUE_TIME] = self.dwd_weather.issue_time
                self.infos[ATTR_STATION_ID] = self.dwd_weather.station_id
                self.infos[ATTR_STATION_NAME] = self.dwd_weather.get_station_name(False)

                _LOGGER.debug(
                    "forecast_data for station_id '{}': {}".format(
                        self.station_id, self.dwd_weather.forecast_data
                    )
                )
                forecast_data = []
                timestep = datetime(
                    timestamp.year, timestamp.month, timestamp.day, tzinfo=timezone.utc
                )
                # Find the next timewindow from actual time
                while timestep < timestamp:
                    timestep += timedelta(hours=self.weather_interval)
                # Reduce by one to include the current timewindow
                timestep -= timedelta(hours=self.weather_interval)
                for _ in range(0, 9):
                    for _ in range(int(24 / self.weather_interval)):
                        temp_max = self.dwd_weather.get_timeframe_max(
                            WeatherDataType.TEMPERATURE,
                            timestep,
                            self.weather_interval,
                            False,
                        )
                        if temp_max is not None:
                            temp_max = int(round(temp_max - 273.1, 0))

                        temp_min = self.dwd_weather.get_timeframe_min(
                            WeatherDataType.TEMPERATURE,
                            timestep,
                            self.weather_interval,
                            False,
                        )
                        if temp_min is not None:
                            temp_min = int(round(temp_min - 273.1, 0))

                        precipitation_prop = self.dwd_weather.get_timeframe_max(
                            WeatherDataType.PRECIPITATION_PROBABILITY,
                            timestep,
                            self.weather_interval,
                            False,
                        )
                        if precipitation_prop is not None:
                            precipitation_prop = int(precipitation_prop)
                        forecast_data.append(
                            {
                                ATTR_FORECAST_TIME: timestep.strftime(
                                    "%Y-%m-%dT%H:00:00Z"
                                ),
                                ATTR_FORECAST_CONDITION: self.dwd_weather.get_timeframe_condition(
                                    timestep,
                                    self.weather_interval,
                                    False,
                                ),
                                ATTR_FORECAST_TEMP: temp_max,
                                ATTR_FORECAST_TEMP_LOW: temp_min,
                                ATTR_FORECAST_PRECIPITATION: self.dwd_weather.get_timeframe_sum(
                                    WeatherDataType.PRECIPITATION,
                                    timestep,
                                    self.weather_interval,
                                    False,
                                ),
                                "precipitation_probability": precipitation_prop,
                            }
                        )
                        timestep += timedelta(hours=self.weather_interval)
                self.forecast = forecast_data

    def get_condition(self):
        return self.dwd_weather.get_forecast_condition(
            datetime.now(timezone.utc), False
        )

    def get_weather_report(self):
        return markdownify(self.dwd_weather.weather_report, strip=["br"])

    def get_weather_value(self, data_type: WeatherDataType):
        value = self.dwd_weather.get_forecast_data(
            data_type,
            datetime.now(timezone.utc),
            False,
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
                value = round(value, 0)
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
                value = round(value, 0)
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
        for key in self.dwd_weather.forecast_data:
            item = self.dwd_weather.forecast_data[key][WeatherDataType.CONDITION.value]
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
        for key in self.dwd_weather.forecast_data:
            if (
                datetime(
                    *(time.strptime(key, "%Y-%m-%dT%H:%M:%S.%fZ")[0:6]),
                    0,
                    timezone.utc,
                )
                < timestamp
            ):
                continue

            item = self.dwd_weather.forecast_data[key]
            value = item[data_type.value]
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
                    value = round(value, 0)
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
                    value = round(value, 0)
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
