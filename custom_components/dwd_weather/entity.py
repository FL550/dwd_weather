"""DWDWeatherEntity class."""
import logging
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import DeviceInfo
from .const import (
    CONF_STATION_NAME,
    DOMAIN,
    DWDWEATHER_COORDINATOR,
    DWDWEATHER_DATA,
    NAME,
)

_LOGGER = logging.getLogger(__name__)


class DWDWeatherEntity:
    """DWDWeatherEntity entity."""

    def __init__(self, hass_data, unique_id, name):
        """Class initialization."""
        self._connector = hass_data[DWDWEATHER_DATA]
        self._coordinator = hass_data[DWDWEATHER_COORDINATOR]
        self._device_id = self._connector.dwd_weather.station_id
        self._unique_id = unique_id
        self._name = name
        self._station_name = self._connector._config[CONF_STATION_NAME]

        super().__init__()

    @property
    def device_info(self) -> DeviceInfo | None:
        if self._device_id is None:
            return None

        return DeviceInfo(
            identifiers={(DOMAIN, self._device_id)},
            manufacturer=NAME,
            model=f"Station {self._device_id}",
            name=self._station_name,
            entry_type=DeviceEntryType.SERVICE,
        )

    async def async_update(self):
        """Schedule a custom update via the common entity update service."""
        await self._coordinator.async_request_refresh()

    async def async_added_to_hass(self) -> None:
        """Set up a listener and load data."""
        self.async_on_remove(
            self._coordinator.async_add_listener(self.async_write_ha_state)
        )

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def unique_id(self):
        """Return the unique of the sensor."""
        return self._unique_id

    @property
    def device_id(self):
        """Return the unique of the sensor."""
        return self._device_id

    @property
    def should_poll(self):
        """No polling needed."""
        return False
