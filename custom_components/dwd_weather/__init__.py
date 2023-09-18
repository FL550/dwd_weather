"""The DWD Weather component."""

import asyncio
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Config, HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .connector import DWDWeatherData
from .const import (
    CONF_STATION_ID,
    CONF_WIND_DIRECTION_TYPE,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_WIND_DIRECTION_TYPE,
    DOMAIN,
    DWDWEATHER_COORDINATOR,
    DWDWEATHER_DATA,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["weather", "sensor"]


async def async_setup(hass: HomeAssistant, config: Config) -> bool:
    """Set up configured DWD Weather."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up DWD Weather as config entry."""
    _LOGGER.debug("Setup with data {}".format(entry.data))

    # TODO only if station was configured
    dwd_weather_data = DWDWeatherData(hass, entry)

    # Coordinator checks for new updates
    dwdweather_coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=f"DWD Weather Coordinator for {entry.data[CONF_STATION_ID]}",
        update_method=dwd_weather_data.async_update,
        update_interval=DEFAULT_SCAN_INTERVAL,
    )

    # Fetch initial data so we have data when entities subscribe
    await dwdweather_coordinator.async_refresh()
    if dwd_weather_data.dwd_weather.forecast_data is None:
        _LOGGER.debug("ConfigEntryNotReady")
        raise ConfigEntryNotReady()

    # Save the data
    dwdweather_hass_data = hass.data.setdefault(DOMAIN, {})
    dwdweather_hass_data[entry.entry_id] = {
        DWDWEATHER_DATA: dwd_weather_data,
        DWDWEATHER_COORDINATOR: dwdweather_coordinator,
    }

    # Setup weather and sensor platforms
    for component in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component)
        )

    return True


async def async_migrate_entry(hass, config_entry: ConfigEntry):
    """Migrate old entry."""
    _LOGGER.debug("Migrating from version %s", config_entry.version)

    if config_entry.version == 1:
        new = {**config_entry.data}
        new["weather_interval"] = 24
        config_entry.data = {**new}
        config_entry.version = 2

    if config_entry.version == 2:
        new = {**config_entry.data}
        new[CONF_WIND_DIRECTION_TYPE] = DEFAULT_WIND_DIRECTION_TYPE
        config_entry.data = {**new}
        config_entry.version = 3

    if config_entry.version == 3:
        new = {**config_entry.data}
        # TODO altes Format in neues uebersetzen
        config_entry.data = {**new}
        config_entry.version = 4

    _LOGGER.info("Migration to version %s successful", config_entry.version)
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
