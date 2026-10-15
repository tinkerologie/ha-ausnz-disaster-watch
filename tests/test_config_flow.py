"""Unit tests for config flow, reconfigure flow, and options flow."""

from unittest.mock import patch

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.ausnz_disaster_watch.config_flow import (
    AustralianDisasterWatchConfigFlow,
    infer_state_from_coordinates,
)
from custom_components.ausnz_disaster_watch.const import (
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
    STATE_ACT,
    STATE_NSW,
    STATE_NT,
    STATE_QLD,
    STATE_SA,
    STATE_TAS,
    STATE_VIC,
    STATE_WA,
)
from homeassistant import config_entries, data_entry_flow
from homeassistant.core import HomeAssistant


def test_infer_state_from_coordinates() -> None:
    """Test state heuristic deduction from geographic coordinates across all states."""
    # Tasmania (Hobart)
    assert infer_state_from_coordinates(-42.8821, 147.3272) == STATE_TAS
    # Western Australia (Perth)
    assert infer_state_from_coordinates(-31.9505, 115.8605) == STATE_WA
    # Northern Territory (Darwin)
    assert infer_state_from_coordinates(-12.4634, 130.8456) == STATE_NT
    # South Australia (Adelaide)
    assert infer_state_from_coordinates(-34.9285, 138.6007) == STATE_SA
    # Victoria (Melbourne)
    assert infer_state_from_coordinates(-37.8136, 144.9631) == STATE_VIC
    # ACT (Canberra)
    assert infer_state_from_coordinates(-35.2809, 149.1300) == STATE_ACT
    # Queensland (Moreton Bay / Brisbane)
    assert infer_state_from_coordinates(-27.2657, 152.9818) == STATE_QLD
    # New South Wales (Sydney)
    assert infer_state_from_coordinates(-33.8688, 151.2093) == STATE_NSW
    # New Zealand (Wellington)
    assert infer_state_from_coordinates(-41.2865, 174.7762) == "NZ"


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
        "custom_components.ausnz_disaster_watch.async_setup_entry",
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
        "custom_components.ausnz_disaster_watch.async_setup_entry",
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


async def test_flow_custom_location_manual(hass: HomeAssistant) -> None:
    """Test setup with custom location manual coordinates."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_STATE: STATE_NSW,
            CONF_LOCATION_MODE: LOCATION_MODE_CUSTOM,
            CONF_RADIUS: 60,
            CONF_OVERRIDE_EMERGENCY: True,
            CONF_EXCLUDE_HAZARD_REDUCTION: True,
        },
    )
    assert result2["step_id"] == "location"

    # Complete with valid manual coordinates
    with patch(
        "custom_components.ausnz_disaster_watch.async_setup_entry",
        return_value=True,
    ):
        result_ok = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            user_input={
                "preset_council": "custom",
                CONF_LOCATION_NAME: "Blue Mountains",
                CONF_LATITUDE: -33.7,
                CONF_LONGITUDE: 150.3,
                CONF_COUNCIL_DASHBOARD_URL: "",
            },
        )
        assert result_ok["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
        assert result_ok["data"][CONF_LOCATION_NAME] == "Blue Mountains"
        assert result_ok["data"][CONF_LATITUDE] == -33.7


async def test_flow_duplicate_abort(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that configuring an existing unique ID aborts cleanly."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )
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
    assert result3["type"] == data_entry_flow.FlowResultType.ABORT
    assert result3["reason"] == "already_configured"


async def test_reconfigure_flow(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test reconfigure flow updates entry parameters."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reconfigure_flow(hass)
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    with patch(
        "custom_components.ausnz_disaster_watch.async_setup_entry",
        return_value=True,
    ):
        result_ok = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_STATE: STATE_QLD,
                CONF_LOCATION_NAME: "Updated Moreton Bay",
                CONF_LATITUDE: -27.2500,
                CONF_LONGITUDE: 153.0000,
                CONF_RADIUS: 75,
                CONF_OVERRIDE_EMERGENCY: False,
                CONF_EXCLUDE_HAZARD_REDUCTION: False,
                CONF_COUNCIL_DASHBOARD_URL: "https://disaster.moretonbay.qld.gov.au",
            },
        )
        assert result_ok["type"] == data_entry_flow.FlowResultType.ABORT
        assert result_ok["reason"] == "reconfigure_successful"
        assert mock_config_entry.data[CONF_LOCATION_NAME] == "Updated Moreton Bay"
        assert mock_config_entry.data[CONF_LATITUDE] == -27.2500
        assert mock_config_entry.data[CONF_RADIUS] == 75


async def test_flow_step_error_branches(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test defensive error checks in config flow steps."""
    flow = AustralianDisasterWatchConfigFlow()
    flow.hass = hass
    flow._user_input = {CONF_STATE: STATE_QLD}

    res_loc = await flow.async_step_location({"preset_council": "custom", CONF_LATITUDE: None, CONF_LONGITUDE: None})
    assert res_loc["errors"] == {"base": "invalid_coordinates"}

    flow._get_reconfigure_entry = lambda: mock_config_entry  # type: ignore[method-assign]
    res_reconf = await flow.async_step_reconfigure({CONF_LATITUDE: "invalid", CONF_LONGITUDE: 150.0})
    assert res_reconf["errors"] == {"base": "invalid_coordinates"}

    res_reconf2 = await flow.async_step_reconfigure({CONF_LATITUDE: -95.0, CONF_LONGITUDE: 150.0})
    assert res_reconf2["errors"] == {"base": "invalid_coordinates"}

    res_reconf3 = await flow.async_step_reconfigure({CONF_LATITUDE: None, CONF_LONGITUDE: 150.0})
    assert res_reconf3["errors"] == {"base": "invalid_coordinates"}


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
