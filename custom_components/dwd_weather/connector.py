import logging
import math
from datetime import datetime, timezone, timedelta

from simple_dwd_weatherforecast import dwdforecast

from homeassistant.components.weather import (
    ATTR_FORECAST_CONDITION,
    ATTR_FORECAST_PRECIPITATION,
    ATTR_FORECAST_TEMP,
    ATTR_FORECAST_TEMP_LOW,
    ATTR_FORECAST_TIME,
)

from .const import (ATTR_LATEST_UPDATE, ATTR_ISSUE_TIME)

_LOGGER = logging.getLogger(__name__)


class DWDWeatherData:

    def __init__(self, hass, latitude, longitude, station_id):
        """Initialize the data object."""
        self._hass = hass
        self.forecast = None

        # Public attributes
        self.latitude = latitude
        self.longitude = longitude
        self.infos = {}

        # Checks if station_id was set by the user
        if (station_id != ""):
            if dwdforecast.is_valid_station_id(station_id):
                self.station_id = station_id
            else:
                raise ValueError("Not a valid station_id")
        else:
            self.station_id = dwdforecast.get_nearest_station_id(
                latitude, longitude)
        # Holds the current data from DWD
        self.dwd_weather = dwdforecast.Weather(self.station_id)

    async def async_update(self):
        """Async wrapper for update method."""
        return await self._hass.async_add_executor_job(self._update)

    def _update(self):
        """Get the latest data from DWD and generate forecast array."""
        self.dwd_weather.update()
        if self.dwd_weather.get_station_name(False) == '':
            _LOGGER.exception("No update possible")
        else:
            _LOGGER.info("Updating ", self.dwd_weather.get_station_name(False))
            self.infos[ATTR_LATEST_UPDATE] = datetime.now(timezone.utc)
            self.infos[ATTR_ISSUE_TIME] = self.dwd_weather.issue_time
            _LOGGER.debug("forecast_data for station_id '{}': {}".format(
                self.station_id, self.dwd_weather.forecast_data))
            forecast_data = []
            timestamp = datetime.now(timezone.utc)
            for x in range(0, 8):
                forecast_data.append({
                    ATTR_FORECAST_TIME:
                        timestamp.strftime("%Y-%m-%d"),
                    ATTR_FORECAST_CONDITION:
                        self.dwd_weather.get_daily_condition(timestamp, False),
                    ATTR_FORECAST_TEMP:
                        self.dwd_weather.get_daily_max(
                            dwdforecast.WeatherDataType.TEMPERATURE, timestamp,
                            False) - 274.1,
                    ATTR_FORECAST_TEMP_LOW:
                        self.dwd_weather.get_daily_min(
                            dwdforecast.WeatherDataType.TEMPERATURE, timestamp,
                            False) - 274.1,
                    ATTR_FORECAST_PRECIPITATION:
                        self.dwd_weather.get_daily_sum(
                            dwdforecast.WeatherDataType.PRECIPITATION,
                            timestamp, False),
                    "precipitation_probability":
                        int(
                            self.dwd_weather.get_daily_max(
                                dwdforecast.WeatherDataType.
                                PRECIPITATION_PROBABILITY, timestamp, False)
                        ),  # ATTR_FORECAST_PRECIPITATION_PROBABILITY
                })
                timestamp = timestamp + timedelta(days=1)
            self.forecast = forecast_data

    def get_condition(self):
        return self.dwd_weather.get_forecast_condition(
            datetime.now(timezone.utc), False)

    def get_temperature(self):
        return self.dwd_weather.get_forecast_data(
            dwdforecast.WeatherDataType.TEMPERATURE, datetime.now(timezone.utc),
            False) - 274.1

    def get_pressure(self):
        return self.dwd_weather.get_forecast_data(
            dwdforecast.WeatherDataType.PRESSURE, datetime.now(timezone.utc),
            False) / 100

    def get_wind_speed(self):
        return round(
            self.dwd_weather.get_forecast_data(
                dwdforecast.WeatherDataType.WIND_SPEED,
                datetime.now(timezone.utc), False), 1)

    def get_wind_direction(self):
        return self.dwd_weather.get_forecast_data(
            dwdforecast.WeatherDataType.WIND_DIRECTION,
            datetime.now(timezone.utc), False)

    def get_visibility(self):
        return round(
            self.dwd_weather.get_forecast_data(
                dwdforecast.WeatherDataType.VISIBILITY,
                datetime.now(timezone.utc), False) / 1000, 1)

    def get_humidity(self):
        rh_c2 = 17.5043
        rh_c3 = 241.2
        T = self.dwd_weather.get_forecast_data(
            dwdforecast.WeatherDataType.TEMPERATURE, datetime.now(timezone.utc),
            False)
        TD = self.dwd_weather.get_forecast_data(
            dwdforecast.WeatherDataType.DEWPOINT, datetime.now(timezone.utc),
            False)
        _LOGGER.debug("T: {}, TD: {}".format(T, TD))
        RH = 100 * math.exp((rh_c2 * TD / (rh_c3 + TD)) - (rh_c2 * T /
                                                           (rh_c3 + T)))
        return round(RH, 1)
