"""The DWD Weather component."""

import logging

from homeassistant.core import Config, HomeAssistant
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE, CONF_NAME
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

# from .config_flow import DWDWeatherConfigFlow  # noqa: F401
from .const import (DOMAIN, DEFAULT_SCAN_INTERVAL, DWDWEATHER_DATA,
                    DWDWEATHER_COORDINATOR, DWDWEATHER_NAME)  # noqa: F401
from .connector import DWDWeatherData

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: Config) -> bool:
    """Set up configured DWD Weather."""
    return True


async def async_setup_entry(hass, entry):
    """Set up DWD Weather as config entry."""

    latitude = entry.data[CONF_LATITUDE]
    longitude = entry.data[CONF_LONGITUDE]
    site_name = entry.data[CONF_NAME]

    dwd_weather_data = DWDWeatherData(hass, latitude, longitude)

    await dwd_weather_data.async_update()
    if dwd_weather_data.weather_data.get_station_name(False) == '':
        raise ConfigEntryNotReady()

    dwdweather_coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=f"DWD Weather Coordinator for {site_name}",
        update_method=dwd_weather_data.async_update,
        update_interval=DEFAULT_SCAN_INTERVAL,
    )

    dwdweather_hass_data = hass.data.setdefault(DOMAIN, {})
    dwdweather_hass_data[entry.entry_id] = {
        DWDWEATHER_DATA: dwd_weather_data,
        DWDWEATHER_COORDINATOR: dwdweather_coordinator,
        DWDWEATHER_NAME: site_name,
    }

    # Fetch initial data so we have data when entities subscribe
    await dwdweather_coordinator.async_refresh()
    if dwd_weather_data.weather_data.get_station_name == '':
        raise ConfigEntryNotReady()
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(entry, "weather"))
    return True


async def async_update(self):
    """Async wrapper for update method."""
    return await self._hass.async_add_executor_job(self._update)


async def async_unload_entry(hass, config_entry):
    """Unload a config entry."""
    await hass.config_entries.async_forward_entry_unload(
        config_entry, "weather")
    return True
