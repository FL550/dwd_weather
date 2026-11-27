"""Tests for the BKG base map below the weather maps."""

from datetime import datetime, timezone
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import MagicMock, PropertyMock, patch
from urllib.parse import parse_qs, urlparse

from PIL import Image
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
import requests

from custom_components.dwd_weather.camera import MyCamera
from custom_components.dwd_weather.config_flow import (
    DWDWeatherConfigFlow,
    OptionsFlowHandler,
)
from custom_components.dwd_weather.connector import DWDMapData
from custom_components.dwd_weather.const import (
    CONF_ENTITY_TYPE,
    CONF_ENTITY_TYPE_MAP,
    CONF_MAP_BACKGROUND_KREISE,
    CONF_MAP_BACKGROUND_TOPPLUS_DARK,
    CONF_MAP_BACKGROUND_TOPPLUS_LIGHT,
    CONF_MAP_BACKGROUND_TYPE,
    CONF_MAP_BASEMAP_BLEND,
    CONF_MAP_CENTERMARKER,
    CONF_MAP_DARK_MODE,
    CONF_MAP_FOREGROUND_MAXTEMP,
    CONF_MAP_FOREGROUND_PRECIPITATION,
    CONF_MAP_FOREGROUND_TYPE,
    CONF_MAP_HOMEMARKER,
    CONF_MAP_ID,
    CONF_MAP_LOOP_SPEED,
    DOMAIN,
    DWDWEATHER_COORDINATOR,
    DWDWEATHER_DATA,
)
from custom_components.dwd_weather.map_loop import FutureImageLoop
from simple_dwd_weatherforecast import basemap
from simple_dwd_weatherforecast.dwdmap import WeatherBackgroundMapType, WeatherMapType

SIZE = (200, 100)
LAND = (240, 230, 220)
RAIN = (0, 0, 255)
WHITE = (255, 255, 255)
NOW = datetime(2026, 11, 25, 21, 0, tzinfo=timezone.utc)


def _png(image: Image.Image) -> bytes:
    raw = BytesIO()
    image.save(raw, format="PNG")
    return raw.getvalue()


def _response(content: bytes) -> MagicMock:
    response = MagicMock()
    response.status_code = 200
    response.headers = {"content-type": "image/png"}
    response.content = content
    return response


@pytest.fixture(autouse=True)
def fresh_basemaps():
    """Base maps are shared per map section; every test starts without one."""
    basemap.get_basemap.cache_clear()
    yield
    basemap.get_basemap.cache_clear()


@pytest.fixture
def servers():
    """DWD sends rain in the left half of a transparent image, BKG plain land.

    The integration and the library share the one requests module, so a single
    patch answers both and tells them apart by the host.
    """
    weather = Image.new("RGBA", SIZE, (0, 0, 0, 0))
    weather.paste((*RAIN, 255), (0, 0, SIZE[0] // 2, SIZE[1]))
    state = SimpleNamespace(bkg_reachable=True, dwd=[], bkg=[])

    def answer(url, *_, **__):
        if urlparse(url).hostname == "maps.dwd.de":
            state.dwd.append(url)
            return _response(_png(weather))
        state.bkg.append(url)
        if not state.bkg_reachable:
            raise requests.ConnectionError
        return _response(_png(Image.new("RGB", SIZE, LAND)))

    with patch("requests.get", side_effect=answer):
        yield state


def _loop(background: WeatherBackgroundMapType, **kwargs) -> FutureImageLoop:
    return FutureImageLoop(
        minx=9.0,
        miny=49.0,
        maxx=10.0,
        maxy=50.0,
        map_types=[WeatherMapType.NIEDERSCHLAGSRADAR],
        background_types=[background],
        image_width=SIZE[0],
        image_height=SIZE[1],
        steps_past=2,
        **kwargs,
    )


def _query(urls: list[str]) -> dict:
    return parse_qs(urlparse(urls[-1]).query)


def test_basemap_below_the_weather(servers):
    """The DWD layer is requested alone and transparent, then put onto the map."""
    loop = _loop(WeatherBackgroundMapType.TOPPLUS_LIGHT)

    image = loop._get_image(NOW)

    query = _query(servers.dwd)
    assert query["layers"] == [WeatherMapType.NIEDERSCHLAGSRADAR.value]
    assert query["transparent"] == ["true"]
    assert image.getpixel((0, 0)) == RAIN
    assert image.getpixel((SIZE[0] - 1, 0)) == LAND
    assert loop.basemap is not None


def test_other_backgrounds_are_unchanged(servers):
    """Without a BKG map nothing is requested from the BKG and nothing changes."""
    loop = _loop(WeatherBackgroundMapType.KREISE)

    loop._get_image(NOW)

    query = _query(servers.dwd)
    assert query["layers"] == [
        f"{WeatherBackgroundMapType.KREISE.value},{WeatherMapType.NIEDERSCHLAGSRADAR.value}"
    ]
    assert "transparent" not in query
    assert servers.bkg == []
    assert loop.basemap is None


def test_blend(servers):
    """With blend the colours of the map and the weather are multiplied."""
    loop = _loop(WeatherBackgroundMapType.TOPPLUS_LIGHT, basemap_blend=True)

    image = loop._get_image(NOW)

    assert image.getpixel((0, 0)) == (0, 0, LAND[2])


def test_frames_are_fetched_again_when_the_basemap_is_back(servers):
    """Frames drawn without the map are not kept once the map is available."""
    servers.bkg_reachable = False
    loop = _loop(WeatherBackgroundMapType.TOPPLUS_LIGHT)

    with patch(
        "custom_components.dwd_weather.map_loop.get_time_last_5_min",
        return_value=NOW,
    ):
        loop.update()
        assert loop._last_complete is False
        assert loop.get_images()[0].getpixel((SIZE[0] - 1, 0)) == WHITE
        fetched = len(servers.dwd)

        servers.bkg_reachable = True
        loop.basemap._retry_after = None
        loop._last_attempt = None
        loop.update()

    assert len(servers.dwd) == 2 * fetched
    assert loop._last_complete is True
    assert loop._basemap_missing is False
    for image in loop.get_images():
        assert image.getpixel((SIZE[0] - 1, 0)) == LAND


def _map_data(background: str, hass=None) -> DWDMapData:
    entry = MockConfigEntry(
        data={
            CONF_MAP_FOREGROUND_TYPE: CONF_MAP_FOREGROUND_PRECIPITATION,
            CONF_MAP_BACKGROUND_TYPE: background,
        }
    )
    return DWDMapData(hass or MagicMock(), entry)


def test_map_types():
    """The two options map to the base map types of the library."""
    map_data = _map_data(CONF_MAP_BACKGROUND_KREISE)

    assert (
        map_data.map_maptype(CONF_MAP_BACKGROUND_TOPPLUS_LIGHT)
        == WeatherBackgroundMapType.TOPPLUS_LIGHT
    )
    assert (
        map_data.map_maptype(CONF_MAP_BACKGROUND_TOPPLUS_DARK)
        == WeatherBackgroundMapType.TOPPLUS_DARK
    )


def test_cache_dir():
    """The map is kept in the cache folder of Home Assistant."""
    hass = MagicMock()
    hass.config.cache_path.return_value = "/config/.cache/dwd_weather"

    map_data = _map_data(CONF_MAP_BACKGROUND_TOPPLUS_LIGHT, hass)

    assert map_data.basemap_cache_dir == "/config/.cache/dwd_weather"
    hass.config.cache_path.assert_called_once_with(DOMAIN)


def test_attribution():
    """The source note is there with a BKG map only."""
    assert _map_data(CONF_MAP_BACKGROUND_KREISE).basemap_attribution is None

    note = _map_data(CONF_MAP_BACKGROUND_TOPPLUS_DARK).basemap_attribution
    assert "dl-de/by-2-0" in note
    assert "Daten verändert" in note

    map_data = _map_data(CONF_MAP_BACKGROUND_TOPPLUS_LIGHT)
    map_data._maploop = MagicMock()
    map_data._maploop.basemap.attribution = "note of the loaded map"
    assert map_data.basemap_attribution == "note of the loaded map"


def test_camera_attribution():
    """The camera shows the source note of its map data."""
    dwd_data = MagicMock()
    dwd_data._configdata = {
        CONF_MAP_FOREGROUND_TYPE: CONF_MAP_FOREGROUND_PRECIPITATION,
        CONF_MAP_ID: "germany_precip",
        CONF_MAP_LOOP_SPEED: 0.5,
    }
    dwd_data.basemap_attribution = "note"
    camera = MyCamera({DWDWEATHER_DATA: dwd_data, DWDWEATHER_COORDINATOR: MagicMock()})

    assert camera.attribution == "note"


def _default(schema, key):
    for field in schema.schema:
        if getattr(field, "schema", None) == key:
            return field.default()
    raise AssertionError(f"{key} not in the form")


@pytest.mark.asyncio
async def test_new_map_offers_blend_off_by_default():
    """The form of a new map has the option, switched off."""
    flow = DWDWeatherConfigFlow()
    flow.hass = MagicMock()
    flow.config_data = {}

    result = await flow.async_step_select_map_content()

    assert _default(result["data_schema"], CONF_MAP_BASEMAP_BLEND) is False


@pytest.mark.parametrize("stored,shown", [(None, False), (True, True)])
@pytest.mark.asyncio
async def test_options_show_blend(stored, shown):
    """Existing maps have no value yet and show the option switched off."""
    flow = OptionsFlowHandler()
    flow.hass = MagicMock()
    config_entry = MagicMock()
    config_entry.data = {
        CONF_ENTITY_TYPE: CONF_ENTITY_TYPE_MAP,
        CONF_MAP_FOREGROUND_TYPE: CONF_MAP_FOREGROUND_MAXTEMP,
        CONF_MAP_BACKGROUND_TYPE: CONF_MAP_BACKGROUND_TOPPLUS_LIGHT,
        CONF_MAP_CENTERMARKER: False,
        CONF_MAP_HOMEMARKER: False,
        CONF_MAP_DARK_MODE: False,
    }
    if stored is not None:
        config_entry.data[CONF_MAP_BASEMAP_BLEND] = stored

    with patch.object(
        OptionsFlowHandler,
        "config_entry",
        new_callable=PropertyMock,
        return_value=config_entry,
    ):
        result = await flow.async_step_init()

    assert _default(result["data_schema"], CONF_MAP_BASEMAP_BLEND) is shown
