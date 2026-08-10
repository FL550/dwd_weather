import sys
from unittest.mock import AsyncMock, MagicMock, patch

if "turbojpeg" not in sys.modules:
    try:
        import turbojpeg  # noqa: F401
    except ImportError:
        sys.modules["turbojpeg"] = MagicMock()

import pytest
from homeassistant.core import HomeAssistant

from custom_components.dwd_weather.camera import MyCamera
from custom_components.dwd_weather.const import (
    CONF_MAP_FOREGROUND_PRECIPITATION,
    CONF_MAP_FOREGROUND_TYPE,
    CONF_MAP_ID,
    CONF_MAP_LOOP_SPEED,
    DOMAIN,
    DWDWEATHER_COORDINATOR,
    DWDWEATHER_DATA,
)


@pytest.fixture
def mock_hass_data():
    """Create mock hass_data dictionary for camera entity."""
    dwd_data = MagicMock()
    dwd_data._configdata = {
        CONF_MAP_FOREGROUND_TYPE: CONF_MAP_FOREGROUND_PRECIPITATION,
        CONF_MAP_ID: "germany_precip",
        CONF_MAP_LOOP_SPEED: 1.5,
    }
    dwd_data._images = [b"image_bytes_1", b"image_bytes_2"]
    dwd_data.get_image.return_value = b"test_camera_image"
    dwd_data.current_label = "Nowcast (+30m)"

    coordinator = MagicMock()
    coordinator.async_add_listener = MagicMock(return_value=MagicMock())
    coordinator.async_request_refresh = AsyncMock()

    return {
        DWDWEATHER_DATA: dwd_data,
        DWDWEATHER_COORDINATOR: coordinator,
    }


def test_camera_properties(mock_hass_data):
    """Test camera entity properties."""
    camera = MyCamera(mock_hass_data)

    assert camera.name == "Precipitation"
    assert camera.unique_id == "map_Precipitation_germany_precip"
    assert camera.translation_key == "weather_maps"
    assert camera.frame_interval == 1.5
    assert camera.state == "Radar"
    assert camera.device_info["name"] == "DWD weather maps"


@pytest.mark.asyncio
async def test_camera_added_to_hass(mock_hass_data):
    """Test async_added_to_hass subscribes to coordinator updates."""
    camera = MyCamera(mock_hass_data)
    camera.hass = MagicMock()
    camera.async_on_remove = MagicMock()

    with patch("homeassistant.components.camera.Camera.async_added_to_hass", AsyncMock()):
        await camera.async_added_to_hass()

    coordinator = mock_hass_data[DWDWEATHER_COORDINATOR]
    assert coordinator.async_add_listener.called
    assert camera.async_on_remove.called


@pytest.mark.asyncio
async def test_async_camera_image(mock_hass_data):
    """Test async_camera_image fetches image and updates state label."""
    camera = MyCamera(mock_hass_data)
    camera.hass = MagicMock()
    camera.async_write_ha_state = MagicMock()

    image_bytes = await camera.async_camera_image(600, 400)

    assert image_bytes == b"test_camera_image"
    dwd_data = mock_hass_data[DWDWEATHER_DATA]
    dwd_data.set_size.assert_called_once_with(600, 400)
    assert camera.state == "Nowcast (+30m)"
    assert camera.async_write_ha_state.called
