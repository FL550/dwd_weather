import logging
from custom_components.dwd_weather.connector import DWDMapData
from homeassistant.components.camera import Camera
from homeassistant.helpers.typing import ConfigType, HomeAssistantType
from simple_dwd_weatherforecast import dwdmap
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.device_registry import DeviceEntryType

from .const import (
    CONF_MAP_ID,
    DOMAIN,
    DWDWEATHER_COORDINATOR,
    DWDWEATHER_DATA,
    NAME,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistantType, entry: ConfigType, async_add_entities
) -> None:
    """Set up the DWD weather camera platform."""
    hass_data = hass.data[DOMAIN][entry.entry_id]
    # if CONF_STATION_ID in entry.data:
    _LOGGER.debug("Camera async_setup_entry")

    async_add_entities(
        [MyCamera(hass_data)],
        False,
    )


class MyCamera(Camera):
    def __init__(self, hass_data):
        """Class initialization."""
        super().__init__()

        dwd_data: DWDMapData = hass_data[DWDWEATHER_DATA]

        self._map_type = "todo"
        self._unique_id = f"map_{self._map_type}_{dwd_data._config[CONF_MAP_ID]}"
        self._name = f"{self._map_type} {dwd_data._config[CONF_MAP_ID]}"

        self._connector: DWDMapData = hass_data[DWDWEATHER_DATA]
        self._coordinator = hass_data[DWDWEATHER_COORDINATOR]

    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Return bytes of camera image."""
        _LOGGER.debug("getting image")
        # TODO respect options
        await self._coordinator.async_request_refresh()
        image = self._connector.get_image()
        return image

    @property
    def name(self):
        """Return the unique of the sensor."""
        return self._name

    @property
    def unique_id(self):
        """Return the unique of the sensor."""
        return self._unique_id

    @property
    def device_info(self) -> DeviceInfo | None:
        return DeviceInfo(
            identifiers={(DOMAIN, "Maps")},
            manufacturer=NAME,
            model="Weather maps",
            name="DWD weather maps",
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    def translation_key(self):
        """Return the current condition."""
        return "weather_maps"
