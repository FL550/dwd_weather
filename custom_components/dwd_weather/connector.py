"""Connector class to retrieve data, which is use by the weather and sensor enities."""
import logging
import math
from datetime import datetime, timedelta, timezone

from homeassistant.components.weather import (
    ATTR_FORECAST_CONDITION,
    ATTR_FORECAST_PRECIPITATION,
    ATTR_FORECAST_TEMP,
    ATTR_FORECAST_TEMP_LOW,
    ATTR_FORECAST_TIME,
)
from simple_dwd_weatherforecast import dwdforecast

from .const import (
    ATTR_ISSUE_TIME,
    ATTR_LATEST_UPDATE,
    ATTR_STATION_ID,
    ATTR_STATION_NAME,
)

_LOGGER = logging.getLogger(__name__)


class DWDWeatherData:
    def __init__(self, hass, latitude, longitude, station_id):
        """Initialize the data object."""
        self._hass = hass
        self.forecast = None
        self.station_id = None
        self.latest_update = None

        # Public attributes
        self.latitude = latitude
        self.longitude = longitude
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
        self.dwd_weather.update()
        if self.dwd_weather.get_station_name(False) == "":
            _LOGGER.exception("No update possible")
        else:
            _LOGGER.info("Updating ", self.dwd_weather.get_station_name(False))
            self.infos[ATTR_LATEST_UPDATE] = datetime.now(timezone.utc)
            self.latest_update = datetime.now(timezone.utc)
            self.infos[ATTR_ISSUE_TIME] = self.dwd_weather.issue_time
            self.infos[ATTR_STATION_ID] = self.dwd_weather.station_id
            self.infos[ATTR_STATION_NAME] = self.dwd_weather.get_station_name(False)

            _LOGGER.debug(
                "forecast_data for station_id '{}': {}".format(
                    self.station_id, self.dwd_weather.forecast_data
                )
            )
            forecast_data = []
            timestamp = datetime.now(timezone.utc)
            for x in range(0, 9):
                temp_max = self.dwd_weather.get_daily_max(
                    dwdforecast.WeatherDataType.TEMPERATURE, timestamp, False
                )
                if temp_max is not None:
                    temp_max -= 273.1

                temp_min = self.dwd_weather.get_daily_min(
                    dwdforecast.WeatherDataType.TEMPERATURE, timestamp, False
                )
                if temp_min is not None:
                    temp_min -= 273.1

                precipitation_prop = self.dwd_weather.get_daily_max(
                    dwdforecast.WeatherDataType.PRECIPITATION_PROBABILITY,
                    timestamp,
                    False,
                )
                if precipitation_prop is not None:
                    precipitation_prop = int(precipitation_prop)
                forecast_data.append(
                    {
                        ATTR_FORECAST_TIME: timestamp.strftime("%Y-%m-%d"),
                        ATTR_FORECAST_CONDITION: self.dwd_weather.get_daily_condition(
                            timestamp, False
                        ),
                        ATTR_FORECAST_TEMP: temp_max,
                        ATTR_FORECAST_TEMP_LOW: temp_min,
                        ATTR_FORECAST_PRECIPITATION: self.dwd_weather.get_daily_sum(
                            dwdforecast.WeatherDataType.PRECIPITATION, timestamp, False
                        ),
                        "precipitation_probability": precipitation_prop,  # ATTR_FORECAST_PRECIPITATION_PROBABILITY
                    }
                )
                timestamp = timestamp + timedelta(days=1)
            self.forecast = forecast_data

    def get_condition(self):
        return self.dwd_weather.get_forecast_condition(
            datetime.now(timezone.utc), False
        )

    def get_temperature(self):
        return (
            self.dwd_weather.get_forecast_data(
                dwdforecast.WeatherDataType.TEMPERATURE,
                datetime.now(timezone.utc),
                False,
            )
            - 273.1
        )

    def get_pressure(self):
        return (
            self.dwd_weather.get_forecast_data(
                dwdforecast.WeatherDataType.PRESSURE, datetime.now(timezone.utc), False
            )
            / 100
        )

    def get_wind_speed(self):
        return round(
            self.dwd_weather.get_forecast_data(
                dwdforecast.WeatherDataType.WIND_SPEED,
                datetime.now(timezone.utc),
                False,
            ) * 3.6,
            1,
        )

    def get_wind_direction(self):
        return self.dwd_weather.get_forecast_data(
            dwdforecast.WeatherDataType.WIND_DIRECTION,
            datetime.now(timezone.utc),
            False,
        )

    def get_visibility(self):
        return round(
            self.dwd_weather.get_forecast_data(
                dwdforecast.WeatherDataType.VISIBILITY,
                datetime.now(timezone.utc),
                False,
            )
            / 1000,
            1,
        )

    def get_humidity(self):
        rh_c2 = 17.5043
        rh_c3 = 241.2
        T = (
            self.dwd_weather.get_forecast_data(
                dwdforecast.WeatherDataType.TEMPERATURE,
                datetime.now(timezone.utc),
                False,
            )
            - 273.1
        )
        TD = (
            self.dwd_weather.get_forecast_data(
                dwdforecast.WeatherDataType.DEWPOINT, datetime.now(timezone.utc), False
            )
            - 273.1
        )
        _LOGGER.debug("T: {}, TD: {}".format(T, TD))
        RH = 100 * math.exp((rh_c2 * TD / (rh_c3 + TD)) - (rh_c2 * T / (rh_c3 + T)))
        return round(RH, 1)

    def get_condition_hourly(self):
        data = []
        for key in self.dwd_weather.forecast_data:
            item = self.dwd_weather.forecast_data[key][
                dwdforecast.WeatherDataType.CONDITION.value
            ]
            if item != "-":
                value = self.dwd_weather.weather_codes[item][0]
            else:
                value = None
            data.append({ATTR_FORECAST_TIME: key, "value": value})
        return data

    def get_temperature_hourly(self):
        data = []
        for key in self.dwd_weather.forecast_data:
            item = self.dwd_weather.forecast_data[key]
            data.append(
                {
                    ATTR_FORECAST_TIME: key,
                    "value": round(
                        item[dwdforecast.WeatherDataType.TEMPERATURE.value] - 273.1, 1
                    ),
                }
            )
        return data

    def get_dewpoint_hourly(self):
        data = []
        for key in self.dwd_weather.forecast_data:
            item = self.dwd_weather.forecast_data[key]
            data.append(
                {
                    ATTR_FORECAST_TIME: key,
                    "value": round(
                        item[dwdforecast.WeatherDataType.DEWPOINT.value] - 273.1, 1
                    ),
                }
            )
        return data

    def get_pressure_hourly(self):
        data = []
        for key in self.dwd_weather.forecast_data:
            item = self.dwd_weather.forecast_data[key]
            data.append(
                {
                    ATTR_FORECAST_TIME: key,
                    "value": round(
                        item[dwdforecast.WeatherDataType.PRESSURE.value] / 100, 1
                    ),
                }
            )
        return data

    def get_wind_speed_hourly(self):
        data = []
        for key in self.dwd_weather.forecast_data:
            item = self.dwd_weather.forecast_data[key]
            data.append(
                {
                    ATTR_FORECAST_TIME: key,
                    "value": item[dwdforecast.WeatherDataType.WIND_SPEED.value],
                }
            )
        return data

    def get_wind_direction_hourly(self):
        data = []
        for key in self.dwd_weather.forecast_data:
            item = self.dwd_weather.forecast_data[key]
            data.append(
                {
                    ATTR_FORECAST_TIME: key,
                    "value": item[dwdforecast.WeatherDataType.WIND_DIRECTION.value],
                }
            )
        return data

    def get_wind_gusts_hourly(self):
        data = []
        for key in self.dwd_weather.forecast_data:
            item = self.dwd_weather.forecast_data[key]
            data.append(
                {
                    ATTR_FORECAST_TIME: key,
                    "value": item[dwdforecast.WeatherDataType.WIND_GUSTS.value],
                }
            )
        return data

    def get_precipitation_hourly(self):
        data = []
        for key in self.dwd_weather.forecast_data:
            item = self.dwd_weather.forecast_data[key]
            data.append(
                {
                    ATTR_FORECAST_TIME: key,
                    "value": item[dwdforecast.WeatherDataType.PRECIPITATION.value],
                }
            )
        return data

    def get_precipitation_probability_hourly(self):
        data = []
        for key in self.dwd_weather.forecast_data:
            item = self.dwd_weather.forecast_data[key]
            data.append(
                {
                    ATTR_FORECAST_TIME: key,
                    "value": item[
                        dwdforecast.WeatherDataType.PRECIPITATION_PROBABILITY.value
                    ],
                }
            )
        return data

    def get_precipitation_duration_hourly(self):
        data = []
        for key in self.dwd_weather.forecast_data:
            item = self.dwd_weather.forecast_data[key]
            data.append(
                {
                    ATTR_FORECAST_TIME: key,
                    "value": item[
                        dwdforecast.WeatherDataType.PRECIPITATION_DURATION.value
                    ],
                }
            )
        return data

    def get_cloud_coverage_hourly(self):
        data = []
        for key in self.dwd_weather.forecast_data:
            item = self.dwd_weather.forecast_data[key]
            data.append(
                {
                    ATTR_FORECAST_TIME: key,
                    "value": item[dwdforecast.WeatherDataType.CLOUD_COVERAGE.value],
                }
            )
        return data

    def get_visibility_hourly(self):
        data = []
        for key in self.dwd_weather.forecast_data:
            item = self.dwd_weather.forecast_data[key]
            data.append(
                {
                    ATTR_FORECAST_TIME: key,
                    "value": round(
                        item[dwdforecast.WeatherDataType.VISIBILITY.value] / 1000, 1
                    ),
                }
            )
        return data

    def get_sun_duration_hourly(self):
        data = []
        for key in self.dwd_weather.forecast_data:
            item = self.dwd_weather.forecast_data[key]
            data.append(
                {
                    ATTR_FORECAST_TIME: key,
                    "value": item[dwdforecast.WeatherDataType.SUN_DURATION.value],
                }
            )
        return data

    def get_sun_irradiance_hourly(self):
        data = []
        for key in self.dwd_weather.forecast_data:
            item = self.dwd_weather.forecast_data[key]
            data.append(
                {
                    ATTR_FORECAST_TIME: key,
                    "value": item[dwdforecast.WeatherDataType.SUN_IRRADIANCE.value],
                }
            )
        return data

    def get_fog_probability_hourly(self):
        data = []
        for key in self.dwd_weather.forecast_data:
            item = self.dwd_weather.forecast_data[key]
            data.append(
                {
                    ATTR_FORECAST_TIME: key,
                    "value": item[dwdforecast.WeatherDataType.FOG_PROBABILITY.value],
                }
            )
        return data

    def get_humidity_hourly(self):
        data = []
        rh_c2 = 17.5043
        rh_c3 = 241.2

        for key in self.dwd_weather.forecast_data:
            T = (
                self.dwd_weather.forecast_data[key][
                    dwdforecast.WeatherDataType.TEMPERATURE.value
                ]
                - 273.1
            )
            TD = (
                self.dwd_weather.forecast_data[key][
                    dwdforecast.WeatherDataType.DEWPOINT.value
                ]
                - 273.1
            )
            RH = 100 * math.exp((rh_c2 * TD / (rh_c3 + TD)) - (rh_c2 * T / (rh_c3 + T)))
            data.append({ATTR_FORECAST_TIME: key, "value": round(RH, 1)})
        return data
