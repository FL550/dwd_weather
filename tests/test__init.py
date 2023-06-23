# pylint: disable=protected-access,redefined-outer-name
"""Test integration_blueprint setup process."""

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.dwd_weather import (
    async_setup_entry,
    async_unload_entry,
    DWDWeatherData,
)
from custom_components.dwd_weather.const import DOMAIN, DWDWEATHER_DATA
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import MOCK_CONFIG


# We can pass fixtures as defined in conftest.py to tell pytest to use the fixture
# for a given test. We can also leverage fixtures and mocks that are available in
# Home Assistant using the pytest_homeassistant_custom_component plugin.
# Assertions allow you to verify that the return value of whatever is on the left
# side of the assertion matches with the right side.
async def test_setup_load_and_unload_entry(hass: HomeAssistant, bypass_get_data):
    """Test entry setup and unload."""
    # Create a mock entry so we don't have to go through config flow
    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG, entry_id="test")

    # Set up the entry and assert that the values set during setup are where we expect
    # them to be.
    assert await async_setup_entry(hass, config_entry)
    assert DOMAIN in hass.data and config_entry.entry_id in hass.data[DOMAIN]
    print(hass.data[DOMAIN][config_entry.entry_id])
    assert isinstance(
        hass.data[DOMAIN][config_entry.entry_id][DWDWEATHER_DATA], DWDWeatherData
    )

    # Unload the entry and verify that the data has been removed
    assert await async_unload_entry(hass, config_entry)
    if DOMAIN in hass.data:
        assert config_entry.entry_id not in hass.data[DOMAIN]


# async def test_setup_entry_exception(hass: HomeAssistant, error_on_get_data):
#     """Test ConfigEntryNotReady when API raises an exception during entry setup."""
#     config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG, entry_id="test")

#     # In this case we are testing the condition where async_setup_entry raises
#     # ConfigEntryNotReady using the `error_on_get_data` fixture which simulates
#     # an error.
#     with pytest.raises(ConfigEntryNotReady):
#         assert await async_setup_entry(hass, config_entry)
