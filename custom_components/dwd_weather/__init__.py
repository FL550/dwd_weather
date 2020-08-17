"""The DWD Weather component."""

import asyncio
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE, CONF_NAME
from homeassistant.core import Config, HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .connector import DWDWeatherData
from .const import (
    CONF_STATION_ID,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    DWDWEATHER_COORDINATOR,
    DWDWEATHER_DATA,
    DWDWEATHER_NAME,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor", "weather"]


async def async_setup(hass: HomeAssistant, config: Config) -> bool:
    """Set up configured DWD Weather."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up DWD Weather as config entry."""

    # Load values from settings
    latitude = entry.data[CONF_LATITUDE]
    longitude = entry.data[CONF_LONGITUDE]
    site_name = entry.data[CONF_NAME]
    station_id = entry.data[CONF_STATION_ID]

    dwd_weather_data = DWDWeatherData(hass, latitude, longitude, station_id)

    # Update data initially
    # await dwd_weather_data.async_update()
    # if dwd_weather_data.weather_data.get_station_name(False) == '':
    #    raise ConfigEntryNotReady()

    # Coordinator checks for new updates
    dwdweather_coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=f"DWD Weather Coordinator for {site_name}",
        update_method=dwd_weather_data.async_update,
        update_interval=DEFAULT_SCAN_INTERVAL,
    )

    # Save the data
    dwdweather_hass_data = hass.data.setdefault(DOMAIN, {})
    dwdweather_hass_data[entry.entry_id] = {
        DWDWEATHER_DATA: dwd_weather_data,
        DWDWEATHER_COORDINATOR: dwdweather_coordinator,
        DWDWEATHER_NAME: site_name,
    }

    # Fetch initial data so we have data when entities subscribe
    await dwdweather_coordinator.async_refresh()
    if dwd_weather_data.dwd_weather.get_station_name == "":
        raise ConfigEntryNotReady()

    for component in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component)
        )

    return True


async def async_update(self):
    """Async wrapper for update method."""
    return await self._hass.async_add_executor_job(self._update)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, component)
                for component in PLATFORMS
            ]
        )
    )
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
        if not hass.data[DOMAIN]:
            hass.data.pop(DOMAIN)
    return unload_ok
