import logging
from datetime import datetime, timezone, timedelta

from simple_dwd_weatherforecast import dwdforecast

from homeassistant.components.weather import (
    ATTR_FORECAST_CONDITION,
    ATTR_FORECAST_PRECIPITATION,
    ATTR_FORECAST_TEMP,
    ATTR_FORECAST_TEMP_LOW,
    ATTR_FORECAST_TIME,
)

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
                self.site_id = station_id
            else:
                raise ValueError("Not a valid station_id")
        else:
            self.site_id = dwdforecast.get_nearest_station_id(
                latitude, longitude)
        # Holds the current data from DWD
        self.weather_data = dwdforecast.Weather(self.site_id)

    async def async_update(self):
        """Async wrapper for update method."""
        return await self._hass.async_add_executor_job(self._update)

    def _update(self):
        """Get the latest data from DWD and generate forecast array."""
        self.weather_data.update()
        if self.weather_data.get_station_name(False) == '':
            _LOGGER.exception("No update possible")
        else:
            _LOGGER.info("Updating ", self.weather_data.get_station_name(False))
            self.infos["latest_update_utc"] = datetime.now(timezone.utc)
            self.infos["forecast_time_utc"] = self.weather_data.issue_time
            _LOGGER.debug("forecast_data for station_id '{}': {}".format(
                self.site_id, self.weather_data.forecast_data))
            forecast_data = []
            timestamp = datetime.now(timezone.utc)
            for x in range(0, 8):
                forecast_data.append({
                    ATTR_FORECAST_TIME:
                        timestamp.strftime("%Y-%m-%d"),
                    ATTR_FORECAST_CONDITION:
                        self.weather_data.get_daily_condition(timestamp, False),
                    ATTR_FORECAST_TEMP:
                        round(
                            float(
                                self.weather_data.get_daily_temp_max(
                                    timestamp, False)), 1),
                    ATTR_FORECAST_TEMP_LOW:
                        round(
                            float(
                                self.weather_data.get_daily_temp_min(
                                    timestamp, False)), 1),
                    ATTR_FORECAST_PRECIPITATION:
                        round(
                            float(
                                self.weather_data.get_daily_precipitation(
                                    timestamp, False)), 1),
                    "precipitation_probability":
                        int(
                            self.weather_data.
                            get_daily_precipitation_probability(
                                timestamp, False)
                        ),  # ATTR_FORECAST_PRECIPITATION_PROBABILITY
                })
                timestamp = timestamp + timedelta(days=1)
            self.forecast = forecast_data
