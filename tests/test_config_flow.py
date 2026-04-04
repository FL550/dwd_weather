"""Tests for config flow."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.data_entry_flow import FlowResultType

from custom_components.dwd_weather.config_flow import DWDWeatherConfigFlow
from custom_components.dwd_weather.const import (
    CONF_CUSTOM_LOCATION,
    CONF_DATA_TYPE,
    CONF_DATA_TYPE_FORECAST,
    CONF_DATA_TYPE_MIXED,
    CONF_DOWNLOAD_AIRQUALITY,
    CONF_DOWNLOAD_APPARENT_TEMPERATURE,
    CONF_ENTITY_TYPE,
    CONF_ENTITY_TYPE_MAP,
    CONF_ENTITY_TYPE_STATION,
    CONF_INTERPOLATE,
    CONF_MAP_TYPE,
    CONF_MAP_TYPE_CUSTOM,
    CONF_MAP_TYPE_GERMANY,
    CONF_SENSOR_FORECAST_STEPS,
    CONF_STATION_ID,
    CONF_STATION_NAME,
)
from .const import MOCK_CONFIG, MOCK_CONFIG_FORECAST


@pytest.mark.asyncio
async def test_user_step_without_input_shows_form():
    """User step with no input should render the initial form."""
    flow = DWDWeatherConfigFlow()
    flow.hass = MagicMock()

    result = await flow.async_step_user()

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"


@pytest.mark.asyncio
async def test_user_step_station_routes_to_station_select():
    """Choosing station entity type should route to station selection step."""
    flow = DWDWeatherConfigFlow()
    flow.hass = MagicMock()
    flow.hass.config.latitude = 52.5
    flow.hass.config.longitude = 13.4

    with (
        patch(
            "custom_components.dwd_weather.config_flow.dwdforecast.get_stations_sorted_by_distance",
            return_value=[("L732", 0)],
        ),
        patch(
            "custom_components.dwd_weather.config_flow.dwdforecast.load_station_id",
            return_value={"report_available": 1, "name": "Berlin", "elev": 34},
        ),
    ):
        result = await flow.async_step_user(
            {CONF_ENTITY_TYPE: CONF_ENTITY_TYPE_STATION}
        )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "station_select"


@pytest.mark.asyncio
async def test_user_step_map_routes_to_map_type():
    """Choosing map entity type should route to map type selection step."""
    flow = DWDWeatherConfigFlow()
    flow.hass = MagicMock()

    result = await flow.async_step_user({CONF_ENTITY_TYPE: CONF_ENTITY_TYPE_MAP})

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "select_map_type"


@pytest.mark.asyncio
async def test_station_select_valid_station_routes_to_report_config():
    """Selecting a report-capable station should route to report config step."""
    flow = DWDWeatherConfigFlow()
    flow.hass = MagicMock()
    flow.hass.config.latitude = 52.5
    flow.hass.config.longitude = 13.4
    flow.config_data = {}

    with patch(
        "custom_components.dwd_weather.config_flow.dwdforecast.load_station_id",
        return_value={"report_available": 1, "name": "Berlin", "elev": 34},
    ):
        result = await flow.async_step_station_select(
            {
                CONF_STATION_ID: "L732",
                CONF_CUSTOM_LOCATION: False,
            }
        )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "station_configure_report"


@pytest.mark.asyncio
async def test_station_configure_creates_entry():
    """Station configure step should create entry when unique id is free."""
    flow = DWDWeatherConfigFlow()
    flow.hass = MagicMock()
    flow.async_set_unique_id = AsyncMock(return_value=None)

    flow.config_data = {
        CONF_STATION_ID: "L732",
        CONF_DATA_TYPE: CONF_DATA_TYPE_FORECAST,
    }

    user_input = {
        CONF_STATION_NAME: "Berlin",
        "wind_direction_type": "degrees",
        CONF_INTERPOLATE: True,
        "hourly_update": False,
        CONF_DOWNLOAD_AIRQUALITY: False,
        CONF_DOWNLOAD_APPARENT_TEMPERATURE: False,
        CONF_SENSOR_FORECAST_STEPS: 10,
        "additional_forecast_attributes": False,
        "daily_temp_high_precision": False,
    }

    result = await flow.async_step_station_configure(user_input)

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_STATION_ID] == "L732"
    assert result["data"][CONF_STATION_NAME] == "Berlin"


@pytest.mark.asyncio
async def test_station_configure_report_stores_data_and_routes():
    """Report config step should store selected data type and continue."""
    flow = DWDWeatherConfigFlow()
    flow.hass = MagicMock()
    flow.config_data = {CONF_STATION_ID: "L732"}

    with patch(
        "custom_components.dwd_weather.config_flow.dwdforecast.load_station_id",
        return_value={"report_available": 1, "name": "Berlin", "elev": 34},
    ):
        result = await flow.async_step_station_configure_report(
            {CONF_DATA_TYPE: CONF_DATA_TYPE_MIXED}
        )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "station_configure"


@pytest.mark.asyncio
async def test_station_select_invalid_station_shows_form_again():
    """Invalid station id should keep user on station selection step."""
    flow = DWDWeatherConfigFlow()
    flow.hass = MagicMock()
    flow.hass.config.latitude = 52.5
    flow.hass.config.longitude = 13.4
    flow.config_data = {}

    with (
        patch(
            "custom_components.dwd_weather.config_flow.dwdforecast.load_station_id",
            side_effect=lambda station_id: (
                None
                if station_id == "INVALID"
                else {"report_available": 1, "name": "Berlin", "elev": 34}
            ),
        ),
        patch(
            "custom_components.dwd_weather.config_flow.dwdforecast.get_stations_sorted_by_distance",
            return_value=[("L732", 0)],
        ),
    ):
        result = await flow.async_step_station_select(
            {CONF_STATION_ID: "INVALID", CONF_CUSTOM_LOCATION: False}
        )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "station_select"


@pytest.mark.asyncio
async def test_station_select_custom_location_uses_nearest_station():
    """Custom location flow should resolve nearest station id before validation."""
    flow = DWDWeatherConfigFlow()
    flow.hass = MagicMock()
    flow.hass.config.latitude = 52.5
    flow.hass.config.longitude = 13.4
    flow.config_data = {}

    with (
        patch(
            "custom_components.dwd_weather.config_flow.dwdforecast.get_nearest_station_id",
            return_value="L732",
        ),
        patch(
            "custom_components.dwd_weather.config_flow.dwdforecast.load_station_id",
            return_value={"report_available": 1, "name": "Berlin", "elev": 34},
        ),
    ):
        result = await flow.async_step_station_select(
            {
                CONF_STATION_ID: "PLACEHOLDER",
                CONF_CUSTOM_LOCATION: True,
                "location_type": {"latitude": 52.51, "longitude": 13.4},
            }
        )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "station_configure_report"


@pytest.mark.asyncio
async def test_station_configure_duplicate_unique_id_shows_form():
    """Duplicate unique id should return to configure form with error."""
    flow = DWDWeatherConfigFlow()
    flow.hass = MagicMock()
    flow.async_set_unique_id = AsyncMock(return_value="existing")
    flow.config_data = {
        CONF_STATION_ID: "L732",
        CONF_DATA_TYPE: CONF_DATA_TYPE_FORECAST,
    }

    result = await flow.async_step_station_configure(
        {
            CONF_STATION_NAME: "Berlin",
            "wind_direction_type": "degrees",
            CONF_INTERPOLATE: True,
            "hourly_update": False,
            CONF_DOWNLOAD_AIRQUALITY: False,
            CONF_DOWNLOAD_APPARENT_TEMPERATURE: False,
            CONF_SENSOR_FORECAST_STEPS: 10,
            "additional_forecast_attributes": False,
            "daily_temp_high_precision": False,
        }
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "station_configure"


@pytest.mark.asyncio
async def test_select_map_type_custom_routes_to_window():
    """Selecting custom map type should route to window selection."""
    flow = DWDWeatherConfigFlow()
    flow.hass = MagicMock()
    flow.config_data = {}
    flow.async_step_select_map_window = AsyncMock(
        return_value={"type": FlowResultType.FORM, "step_id": "select_map_window"}
    )

    result = await flow.async_step_select_map_type(
        {CONF_MAP_TYPE: CONF_MAP_TYPE_CUSTOM}
    )

    assert result["step_id"] == "select_map_window"


@pytest.mark.asyncio
async def test_select_map_type_germany_routes_to_content():
    """Selecting germany map type should route to content step."""
    flow = DWDWeatherConfigFlow()
    flow.hass = MagicMock()
    flow.config_data = {}
    flow.async_step_select_map_content = AsyncMock(
        return_value={"type": FlowResultType.FORM, "step_id": "select_map_content"}
    )

    result = await flow.async_step_select_map_type(
        {CONF_MAP_TYPE: CONF_MAP_TYPE_GERMANY}
    )

    assert result["step_id"] == "select_map_content"


def test_config_constants_are_consistent():
    """Basic consistency checks for config constants used in tests."""
    assert MOCK_CONFIG[CONF_ENTITY_TYPE] == CONF_ENTITY_TYPE_STATION
    assert MOCK_CONFIG_FORECAST[CONF_DATA_TYPE] == CONF_DATA_TYPE_FORECAST
