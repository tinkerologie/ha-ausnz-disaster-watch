"""Unit tests for config flow and options flow."""

from unittest.mock import patch

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.aus_emergency_hazards.config_flow import infer_state_from_coordinates
from custom_components.aus_emergency_hazards.const import (
    CONF_COUNCIL_DASHBOARD_URL,
    CONF_EXCLUDE_HAZARD_REDUCTION,
    CONF_LATITUDE,
    CONF_LOCATION_MODE,
    CONF_LOCATION_NAME,
    CONF_LONGITUDE,
    CONF_OVERRIDE_EMERGENCY,
    CONF_RADIUS,
    CONF_STATE,
    DOMAIN,
    LOCATION_MODE_CUSTOM,
    LOCATION_MODE_HOME,
    STATE_NSW,
    STATE_QLD,
    STATE_VIC,
    STATE_WA,
)
from homeassistant import config_entries, data_entry_flow
from homeassistant.core import HomeAssistant


def test_infer_state_from_coordinates() -> None:
    """Test state heuristic deduction from geographic coordinates."""
    # Queensland (Moreton Bay / Brisbane)
    assert infer_state_from_coordinates(-27.2657, 152.9818) == STATE_QLD
    # New South Wales (Sydney)
    assert infer_state_from_coordinates(-33.8688, 151.2093) == STATE_NSW
    # Victoria (Melbourne)
    assert infer_state_from_coordinates(-37.8136, 144.9631) == STATE_VIC
    # Western Australia (Perth)
    assert infer_state_from_coordinates(-31.9505, 115.8605) == STATE_WA


async def test_flow_user_step_home_mode(hass: HomeAssistant) -> None:
    """Test standard setup using Home Zone location."""
    hass.config.latitude = -27.4698
    hass.config.longitude = 153.0251
    hass.config.location_name = "My Home"

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "user"

    with patch(
        "custom_components.aus_emergency_hazards.async_setup_entry",
        return_value=True,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_STATE: STATE_QLD,
                CONF_LOCATION_MODE: LOCATION_MODE_HOME,
                CONF_RADIUS: 45,
                CONF_OVERRIDE_EMERGENCY: True,
                CONF_EXCLUDE_HAZARD_REDUCTION: True,
            },
        )
        assert result2["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
        assert result2["data"][CONF_STATE] == STATE_QLD
        assert result2["data"][CONF_RADIUS] == 45
        assert result2["data"][CONF_LATITUDE] == -27.4698
        assert result2["data"][CONF_LONGITUDE] == 153.0251
        assert result2["data"][CONF_LOCATION_NAME] == "My Home"


async def test_flow_custom_location_moreton_bay(hass: HomeAssistant) -> None:
    """Test setup with custom location selecting Moreton Bay preset council."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM

    # Select Custom Location mode
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_STATE: STATE_QLD,
            CONF_LOCATION_MODE: LOCATION_MODE_CUSTOM,
            CONF_RADIUS: 50,
            CONF_OVERRIDE_EMERGENCY: True,
            CONF_EXCLUDE_HAZARD_REDUCTION: True,
        },
    )
    assert result2["type"] == data_entry_flow.FlowResultType.FORM
    assert result2["step_id"] == "location"

    with patch(
        "custom_components.aus_emergency_hazards.async_setup_entry",
        return_value=True,
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            user_input={
                "preset_council": "moreton_bay",
                CONF_LOCATION_NAME: "City of Moreton Bay",
                CONF_LATITUDE: -27.2657,
                CONF_LONGITUDE: 152.9818,
                CONF_COUNCIL_DASHBOARD_URL: "https://disaster.moretonbay.qld.gov.au",
            },
        )
        assert result3["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
        assert result3["data"][CONF_LOCATION_NAME] == "City of Moreton Bay"
        assert result3["data"][CONF_COUNCIL_DASHBOARD_URL] == "https://disaster.moretonbay.qld.gov.au"


async def test_options_flow(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test modifying options via Options Flow."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "init"

    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_RADIUS: 75,
            CONF_OVERRIDE_EMERGENCY: False,
            CONF_EXCLUDE_HAZARD_REDUCTION: False,
            CONF_COUNCIL_DASHBOARD_URL: "https://disaster.sunshinecoast.qld.gov.au",
        },
    )
    assert result2["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert mock_config_entry.options[CONF_RADIUS] == 75
    assert mock_config_entry.options[CONF_OVERRIDE_EMERGENCY] is False
    assert mock_config_entry.options[CONF_EXCLUDE_HAZARD_REDUCTION] is False
    assert mock_config_entry.options[CONF_COUNCIL_DASHBOARD_URL] == "https://disaster.sunshinecoast.qld.gov.au"
