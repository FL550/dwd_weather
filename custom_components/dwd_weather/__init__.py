"""The DWD Weather component."""

import asyncio
from datetime import timedelta
import logging
import random

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.helpers.entity_registry import async_migrate_entries
from homeassistant.helpers.typing import ConfigType
from homeassistant.core import callback
from simple_dwd_weatherforecast import dwdforecast

from .connector import DWDMapData, DWDWeatherData
from .const import (
    CONF_DAILY_TEMP_HIGH_PRECISION,
    CONF_DATA_TYPE,
    CONF_DATA_TYPE_FORECAST,
    CONF_ENTITY_TYPE,
    CONF_ENTITY_TYPE_MAP,
    CONF_ENTITY_TYPE_STATION,
    CONF_HOURLY_UPDATE,
    CONF_INTERPOLATE,
    CONF_MAP_HOMEMARKER_COLOR,
    CONF_MAP_HOMEMARKER_SHAPE,
    CONF_MAP_HOMEMARKER_SHAPE_CIRCLE,
    CONF_MAP_HOMEMARKER_SIZE,
    CONF_MAP_LOOP_COUNT,
    CONF_MAP_LOOP_SPEED,
    CONF_MAP_CENTERMARKER,
    CONF_MAP_HOMEMARKER,
    CONF_MAP_TIMESTAMP,
    CONF_ADDITIONAL_FORECAST_ATTRIBUTES,
    CONF_MAP_DARK_MODE,
    CONF_SENSOR_FORECAST_STEPS,
    CONF_STATION_ID,
    CONF_STATION_NAME,
    CONF_WIND_DIRECTION_TYPE,
    DEFAULT_INTERPOLATION,
    DEFAULT_MAP_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_WIND_DIRECTION_TYPE,
    DOMAIN,
    DWDWEATHER_COORDINATOR,
    DWDWEATHER_DATA,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["weather", "sensor"]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up configured DWD Weather."""
    return True


async def update_listener(hass, entry):
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up DWD Weather as config entry."""
    _LOGGER.debug("Setup with data {}".format(entry.data))
    entry.async_on_unload(entry.add_update_listener(update_listener))
    random_delay = random.randint(1, 59)
    if entry.data[CONF_ENTITY_TYPE] == CONF_ENTITY_TYPE_STATION:
        dwd_weather_data = DWDWeatherData(hass, entry)

        # Coordinator checks for new updates
        dwdweather_coordinator = DataUpdateCoordinator(
            hass,
            _LOGGER,
            name=f"DWD Weather Coordinator for {entry.data[CONF_STATION_ID]}",
            update_method=dwd_weather_data.async_update,
            update_interval=DEFAULT_SCAN_INTERVAL + timedelta(seconds=random_delay),
        )

        # Fetch initial data so we have data when entities subscribe
        if dwd_weather_data.dwd_weather.forecast_data is None:
            await dwdweather_coordinator.async_refresh()
        _LOGGER.debug("issue_time: {}".format(dwd_weather_data.dwd_weather.issue_time))
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
            await hass.config_entries.async_forward_entry_setups(entry, [component])

    elif entry.data[CONF_ENTITY_TYPE] == CONF_ENTITY_TYPE_MAP:
        dwd_weather_data = DWDMapData(hass, entry)

        # Coordinator checks for new updates
        dwdweather_coordinator = DataUpdateCoordinator(
            hass,
            _LOGGER,
            name="DWD Map Coordinator",
            update_method=dwd_weather_data.async_update,
            update_interval=DEFAULT_MAP_INTERVAL + timedelta(seconds=random_delay),
        )
        # Save the data
        dwdweather_hass_data = hass.data.setdefault(DOMAIN, {})
        dwdweather_hass_data[entry.entry_id] = {
            DWDWEATHER_DATA: dwd_weather_data,
            DWDWEATHER_COORDINATOR: dwdweather_coordinator,
        }

        await hass.config_entries.async_forward_entry_setups(entry, ["camera"])

    return True


async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry):
    """Migrate old entry."""
    _LOGGER.debug("Migrating from version %s", config_entry.version)

    if config_entry.version == 1:
        new = {**config_entry.data}
        new["weather_interval"] = 24
        hass.config_entries.async_update_entry(config_entry, data=new, version=2)
    elif config_entry.version == 2:
        new = {**config_entry.data}
        new[CONF_WIND_DIRECTION_TYPE] = DEFAULT_WIND_DIRECTION_TYPE
        hass.config_entries.async_update_entry(config_entry, data=new, version=3)
    elif config_entry.version == 3:
        new = {}
        new[CONF_DATA_TYPE] = CONF_DATA_TYPE_FORECAST
        new[CONF_STATION_ID] = dwdforecast.get_nearest_station_id(
            config_entry.data["latitude"], config_entry.data["longitude"]
        )
        new[CONF_STATION_NAME] = config_entry.data["name"]
        new[CONF_WIND_DIRECTION_TYPE] = config_entry.data[CONF_WIND_DIRECTION_TYPE]
        new[CONF_HOURLY_UPDATE] = False
        _LOGGER.debug("Old Config entry {}".format(config_entry.data))

        @callback
        def update_unique_id(entity_entry):
            """Update unique ID of entity entry."""
            new_id = f"{new[CONF_STATION_ID]}_{entity_entry.unique_id.split('_')[0]}"
            _LOGGER.debug(
                "updating entity_id {} from {} to {}".format(
                    entity_entry.entity_id, entity_entry.unique_id, new_id
                )
            )
            return {"new_unique_id": new_id}

        await async_migrate_entries(hass, config_entry.entry_id, update_unique_id)

        hass.config_entries.async_update_entry(config_entry, data=new, version=4)
        _LOGGER.debug("New Config entry {}".format(config_entry.data))
    elif config_entry.version == 4:
        new = {**config_entry.data}
        new[CONF_INTERPOLATE] = DEFAULT_INTERPOLATION
        hass.config_entries.async_update_entry(config_entry, data=new, version=5)
    elif config_entry.version == 5:
        new = {**config_entry.data}
        new[CONF_ENTITY_TYPE] = CONF_ENTITY_TYPE_STATION
        hass.config_entries.async_update_entry(config_entry, data=new, version=6)
    elif config_entry.version == 6:
        new = {**config_entry.data}
        new[CONF_MAP_CENTERMARKER] = True
        new[CONF_MAP_TIMESTAMP] = True
        new[CONF_MAP_LOOP_COUNT] = 6
        new[CONF_MAP_LOOP_SPEED] = 0.5
        hass.config_entries.async_update_entry(config_entry, data=new, version=7)
    elif config_entry.version == 7:
        new = {**config_entry.data}
        new[CONF_MAP_HOMEMARKER] = False
        new[CONF_MAP_HOMEMARKER_SHAPE] = CONF_MAP_HOMEMARKER_SHAPE_CIRCLE
        new[CONF_MAP_HOMEMARKER_SIZE] = 15
        new[CONF_MAP_HOMEMARKER_COLOR] = [255, 0, 0]
        # Skip version 8 as some already have this config with an error. Version 9 is correct
        hass.config_entries.async_update_entry(config_entry, data=new, version=9)
    elif config_entry.version == 8:
        new = {**config_entry.data}
        # If someone is on version 8, add the missing config items.
        new[CONF_MAP_HOMEMARKER_SHAPE] = CONF_MAP_HOMEMARKER_SHAPE_CIRCLE
        new[CONF_MAP_HOMEMARKER_SIZE] = 15
        new[CONF_MAP_HOMEMARKER_COLOR] = [255, 0, 0]
        hass.config_entries.async_update_entry(config_entry, data=new, version=9)
    elif config_entry.version == 9:
        new = {**config_entry.data}
        new[CONF_ADDITIONAL_FORECAST_ATTRIBUTES] = False
        new[CONF_MAP_DARK_MODE] = False
        hass.config_entries.async_update_entry(config_entry, data=new, version=10)
    elif config_entry.version == 10:
        new = {**config_entry.data}
        new[CONF_SENSOR_FORECAST_STEPS] = 250
        hass.config_entries.async_update_entry(config_entry, data=new, version=11)
    elif config_entry.version == 11:
        new = {**config_entry.data}
        new[CONF_DAILY_TEMP_HIGH_PRECISION] = False
        hass.config_entries.async_update_entry(config_entry, data=new, version=12)

    _LOGGER.info("Migration to version %s successful", config_entry.version)
    return True


async def async_update(self):
    """Async wrapper for update method."""
    return await self._hass.async_add_executor_job(self._update)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    if entry.data[CONF_ENTITY_TYPE] == CONF_ENTITY_TYPE_STATION:
        unload_ok = all(
            await asyncio.gather(
                *[
                    hass.config_entries.async_forward_entry_unload(entry, component)
                    for component in PLATFORMS
                ]
            )
        )
    elif entry.data[CONF_ENTITY_TYPE] == CONF_ENTITY_TYPE_MAP:
        unload_ok = all(
            await asyncio.gather(
                hass.config_entries.async_forward_entry_unload(entry, "camera")
            )
        )
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
        if not hass.data[DOMAIN]:
            hass.data.pop(DOMAIN)
    return unload_ok
