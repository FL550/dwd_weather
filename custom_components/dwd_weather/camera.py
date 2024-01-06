import logging
from custom_components.dwd_weather.connector import DWDMapData
from homeassistant.components.camera import Camera
from homeassistant.helpers.typing import ConfigType, HomeAssistantType
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.device_registry import DeviceEntryType

from .const import (
    CONF_MAP_BACKGROUND_TYPE,
    CONF_MAP_ID,
    CONF_MAP_TYPE,
    CONF_MAP_TYPE_CUSTOM,
    CONF_MAP_WINDOW,
    DOMAIN,
    DWDWEATHER_COORDINATOR,
    DWDWEATHER_DATA,
    NAME,
    CONF_MAP_FOREGROUND_TYPE,
    conversion_table_map_foreground,
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

        self._dwd_data: DWDMapData = hass_data[DWDWEATHER_DATA]

        self._map_type = conversion_table_map_foreground[
            self._dwd_data._config[CONF_MAP_FOREGROUND_TYPE]
        ]
        self._unique_id = f"map_{self._map_type}_{self._dwd_data._config[CONF_MAP_ID]}"
        self._name = f"{self._map_type}"

        self._dwd_data.set_type(self._dwd_data._config[CONF_MAP_TYPE])

        if self._dwd_data._config[CONF_MAP_TYPE] == CONF_MAP_TYPE_CUSTOM:
            self._dwd_data.set_location(
                self._dwd_data._config[CONF_MAP_WINDOW]["latitude"],
                self._dwd_data._config[CONF_MAP_WINDOW]["longitude"],
                self._dwd_data._config[CONF_MAP_WINDOW]["radius"],
            )

        self._dwd_data.set_map_style(
            self._dwd_data._config[CONF_MAP_FOREGROUND_TYPE],
            self._dwd_data._config[CONF_MAP_BACKGROUND_TYPE],
        )
        self._coordinator = hass_data[DWDWEATHER_COORDINATOR]

    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Return bytes of camera image."""
        _LOGGER.debug("getting image")
        self._dwd_data.set_size(width if width else 520, height if height else 580)
        await self._coordinator.async_request_refresh()
        image = self._dwd_data.get_image()
        return image

    @property
    def name(self):
        """Return the unique of the sensor."""
        return self._name

    @property
    def unique_id(self):
        """Return the unique of the sensor."""
        _LOGGER.debug("camera unique id: {}".format(self._unique_id))
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
