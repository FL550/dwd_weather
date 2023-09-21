
import logging
from homeassistant.components.camera import Camera
from homeassistant.helpers.typing import ConfigType, HomeAssistantType

from .const import (
    ATTR_ISSUE_TIME,
    ATTR_LATEST_UPDATE,
    ATTR_STATION_ID,
    ATTR_STATION_NAME,
    ATTRIBUTION,
    CONF_STATION_ID,
    CONF_STATION_NAME,
    DOMAIN,
    DWDWEATHER_DATA,
)

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistantType, entry: ConfigType, async_add_entities
) -> None:
    """Set up the DWD weather sensor platform."""
    hass_data = hass.data[DOMAIN][entry.entry_id]
    #if CONF_STATION_ID in entry.data:
    _LOGGER.debug("Camera async_setup_entry")

    async_add_entities(
        [
            MyCamera()
        ],
        False,
    )

class MyCamera(Camera):
    # TODO init

    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Return bytes of camera image."""
