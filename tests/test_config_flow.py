"""Unit tests for config flow, reconfigure flow, and options flow."""

from typing import Any
from unittest.mock import patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.ausnz_disaster_watch.config_flow import (
    VIC_BOUNDARY,
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

RECONFIGURE_INPUT: dict[str, Any] = {
    CONF_STATE: STATE_QLD,
    CONF_LOCATION_NAME: "City of Moreton Bay",
    CONF_LATITUDE: -27.2657,
    CONF_LONGITUDE: 152.9818,
    CONF_RADIUS: 50,
    CONF_OVERRIDE_EMERGENCY: True,
    CONF_EXCLUDE_HAZARD_REDUCTION: True,
    CONF_COUNCIL_DASHBOARD_URL: "https://disaster.moretonbay.qld.gov.au",
}


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


@pytest.mark.parametrize(
    ("town", "lat", "lon", "expected"),
    [
        # Murray River border towns (#6): VIC on the south bank, NSW on the north bank
        ("Mildura", -34.19, 142.16, STATE_VIC),
        ("Buronga NSW", -34.17, 142.18, STATE_NSW),
        ("Wodonga", -36.12, 146.89, STATE_VIC),
        ("Albury", -36.08, 146.92, STATE_NSW),
        ("Echuca", -36.13, 144.75, STATE_VIC),
        ("Moama NSW", -36.11, 144.76, STATE_NSW),
        ("Swan Hill", -35.34, 143.55, STATE_VIC),
        ("Cobram", -35.92, 145.65, STATE_VIC),
        ("Barooga NSW", -35.91, 145.69, STATE_NSW),
        ("Corowa NSW", -36.00, 146.39, STATE_NSW),
        ("Robinvale", -34.58, 142.77, STATE_VIC),
        ("Euston NSW", -34.58, 142.74, STATE_NSW),
        ("Wentworth NSW", -34.11, 141.92, STATE_NSW),
        ("Corryong", -36.20, 147.90, STATE_VIC),
        ("Khancoban NSW", -36.22, 148.13, STATE_NSW),
        # Straight-line border to Cape Howe
        ("Mallacoota", -37.56, 149.75, STATE_VIC),
        ("Eden NSW", -37.07, 149.90, STATE_NSW),
        ("Bombala NSW", -36.91, 149.24, STATE_NSW),
        # Elsewhere in Victoria
        ("Melbourne", -37.81, 144.96, STATE_VIC),
        ("Portland", -38.34, 141.60, STATE_VIC),
        ("Lakes Entrance", -37.88, 147.98, STATE_VIC),
        # Southern NSW that the old "lat < -34" rule called Victoria
        ("Wagga Wagga", -35.12, 147.37, STATE_NSW),
        ("Goulburn", -34.75, 149.72, STATE_NSW),
        ("Wollongong", -34.42, 150.89, STATE_NSW),
        ("Nowra", -34.88, 150.60, STATE_NSW),
        # SA border and the SA latitude bound
        ("Mount Gambier", -37.83, 140.78, STATE_SA),
        ("Renmark", -34.17, 140.75, STATE_SA),
        ("Coober Pedy", -29.01, 134.75, STATE_SA),
        ("Mount Isa", -20.73, 139.49, STATE_QLD),
        ("Birdsville", -25.90, 139.35, STATE_QLD),
        ("Alice Springs", -23.70, 133.88, STATE_NT),
    ],
)
def test_infer_state_border_towns(town: str, lat: float, lon: float, expected: str) -> None:
    """Test the default state for towns near state borders (#6)."""
    assert infer_state_from_coordinates(lat, lon) == expected, town


def test_vic_boundary_size() -> None:
    """Test the Victoria boundary stays a simplified polygon."""
    assert 40 <= len(VIC_BOUNDARY) <= 60


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
        # Home-zone entries follow the home location, so no coordinates are stored (#19)
        assert CONF_LATITUDE not in result2["data"]
        assert CONF_LONGITUDE not in result2["data"]
        assert result2["data"][CONF_LOCATION_NAME] == "My Home"


@pytest.mark.parametrize(
    ("home", "expected_url"),
    [
        ((-16.92, 145.77), "https://disaster.cairns.qld.gov.au"),  # Cairns
        ((-27.10, 152.95), "https://disaster.moretonbay.qld.gov.au"),  # Caboolture
        ((-23.44, 144.25), None),  # Longreach: no preset within 40 km
    ],
)
async def test_flow_home_mode_picks_nearest_council(
    hass: HomeAssistant, home: tuple[float, float], expected_url: str | None
) -> None:
    """A QLD home-zone entry gets the nearest preset dashboard, not always Moreton Bay (#19)."""
    hass.config.latitude, hass.config.longitude = home
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    with patch("custom_components.ausnz_disaster_watch.async_setup_entry", return_value=True):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_STATE: STATE_QLD,
                CONF_LOCATION_MODE: LOCATION_MODE_HOME,
                CONF_RADIUS: 50,
                CONF_OVERRIDE_EMERGENCY: True,
                CONF_EXCLUDE_HAZARD_REDUCTION: True,
            },
        )
    assert result2["data"][CONF_COUNCIL_DASHBOARD_URL] == expected_url


async def test_reconfigure_home_entry_prefills_home_and_switches_to_custom(hass: HomeAssistant) -> None:
    """Reconfigure shows the current home location; choosing a fixed location stores it (#19)."""
    hass.config.latitude, hass.config.longitude = -19.26, 146.82
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_STATE: STATE_QLD,
            CONF_LOCATION_MODE: LOCATION_MODE_HOME,
            CONF_LATITUDE: -27.2,
            CONF_LONGITUDE: 153.0,
        },
    )
    entry.add_to_hass(hass)
    result = await entry.start_reconfigure_flow(hass)
    defaults = {str(key): key.default() for key in result["data_schema"].schema}
    assert defaults[CONF_LATITUDE] == -19.26
    assert defaults[CONF_LONGITUDE] == 146.82

    with patch("custom_components.ausnz_disaster_watch.async_setup_entry", return_value=True):
        await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_STATE: STATE_QLD,
                CONF_LOCATION_NAME: "Townsville",
                CONF_LATITUDE: -19.26,
                CONF_LONGITUDE: 146.82,
                CONF_RADIUS: 50,
                CONF_OVERRIDE_EMERGENCY: True,
                CONF_EXCLUDE_HAZARD_REDUCTION: True,
            },
        )
    # Submitting the displayed home location unchanged keeps following home and drops the
    # coordinates an older version stored
    assert entry.data[CONF_LOCATION_MODE] == LOCATION_MODE_HOME
    assert CONF_LATITUDE not in entry.data
    assert CONF_LONGITUDE not in entry.data

    with patch("custom_components.ausnz_disaster_watch.async_setup_entry", return_value=True):
        result = await entry.start_reconfigure_flow(hass)
        await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_STATE: STATE_QLD,
                CONF_LOCATION_MODE: LOCATION_MODE_CUSTOM,
                CONF_LOCATION_NAME: "Townsville",
                CONF_LATITUDE: -19.26,
                CONF_LONGITUDE: 146.82,
                CONF_RADIUS: 50,
                CONF_OVERRIDE_EMERGENCY: True,
                CONF_EXCLUDE_HAZARD_REDUCTION: True,
            },
        )
    assert entry.data[CONF_LOCATION_MODE] == LOCATION_MODE_CUSTOM
    assert entry.data[CONF_LATITUDE] == -19.26


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


async def test_reconfigure_syncs_options(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test reconfigured values also land in entry.options, which win at runtime (#6)."""
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry,
        options={CONF_RADIUS: 30, CONF_OVERRIDE_EMERGENCY: True, "unrelated": "kept"},
    )

    result = await mock_config_entry.start_reconfigure_flow(hass)
    with patch("custom_components.ausnz_disaster_watch.async_setup_entry", return_value=True):
        result_ok = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={**RECONFIGURE_INPUT, CONF_RADIUS: 100, CONF_OVERRIDE_EMERGENCY: False},
        )
    assert result_ok["type"] == data_entry_flow.FlowResultType.ABORT
    assert result_ok["reason"] == "reconfigure_successful"
    assert mock_config_entry.data[CONF_RADIUS] == 100
    assert mock_config_entry.options[CONF_RADIUS] == 100
    assert mock_config_entry.options[CONF_OVERRIDE_EMERGENCY] is False
    assert mock_config_entry.options["unrelated"] == "kept"
    effective = {**mock_config_entry.data, **mock_config_entry.options}
    assert effective[CONF_RADIUS] == 100
    # Unchanged identity keeps the unique ID
    assert mock_config_entry.unique_id == "ausnz_disaster_watch_qld_city_of_moreton_bay"


async def test_reconfigure_updates_unique_id_and_title(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test changing state and location recomputes the unique ID and title (#6)."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reconfigure_flow(hass)
    with patch("custom_components.ausnz_disaster_watch.async_setup_entry", return_value=True):
        result_ok = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                **RECONFIGURE_INPUT,
                CONF_STATE: STATE_VIC,
                CONF_LOCATION_NAME: "Mildura",
                CONF_LATITUDE: -34.19,
                CONF_LONGITUDE: 142.16,
                CONF_COUNCIL_DASHBOARD_URL: "",
            },
        )
    assert result_ok["reason"] == "reconfigure_successful"
    assert mock_config_entry.unique_id == "ausnz_disaster_watch_vic_mildura"
    assert mock_config_entry.title == "Australia and New Zealand Disaster Watch (VIC - Mildura)"
    assert mock_config_entry.data[CONF_STATE] == STATE_VIC


async def test_reconfigure_home_entry_moving_becomes_custom(
    hass: HomeAssistant,
) -> None:
    """Test a home-zone entry keeps its home ID until its coordinates change."""
    hass.config.latitude = RECONFIGURE_INPUT[CONF_LATITUDE]
    hass.config.longitude = RECONFIGURE_INPUT[CONF_LONGITUDE]
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Australia and New Zealand Disaster Watch (QLD - Home)",
        data={**RECONFIGURE_INPUT, CONF_LOCATION_MODE: LOCATION_MODE_HOME, CONF_LOCATION_NAME: "Home"},
        unique_id="ausnz_disaster_watch_qld_home",
    )
    entry.add_to_hass(hass)

    with patch("custom_components.ausnz_disaster_watch.async_setup_entry", return_value=True):
        result = await entry.start_reconfigure_flow(hass)
        result_ok = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={**RECONFIGURE_INPUT, CONF_LOCATION_NAME: "Home", CONF_RADIUS: 80},
        )
        assert result_ok["reason"] == "reconfigure_successful"
        assert entry.unique_id == "ausnz_disaster_watch_qld_home"
        assert entry.data[CONF_LOCATION_MODE] == LOCATION_MODE_HOME

        result = await entry.start_reconfigure_flow(hass)
        result_ok = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={**RECONFIGURE_INPUT, CONF_LOCATION_NAME: "Caboolture", CONF_LATITUDE: -27.08},
        )
        assert result_ok["reason"] == "reconfigure_successful"
        assert entry.unique_id == "ausnz_disaster_watch_qld_caboolture"
        assert entry.data[CONF_LOCATION_MODE] == LOCATION_MODE_CUSTOM


async def test_reconfigure_home_entry_without_coordinates(
    hass: HomeAssistant,
) -> None:
    """Test a home-zone entry without stored coordinates becomes a custom location."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_STATE: STATE_QLD, CONF_LOCATION_MODE: LOCATION_MODE_HOME},
        unique_id="ausnz_disaster_watch_qld_home",
    )
    entry.add_to_hass(hass)

    with patch("custom_components.ausnz_disaster_watch.async_setup_entry", return_value=True):
        result = await entry.start_reconfigure_flow(hass)
        result_ok = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={**RECONFIGURE_INPUT, CONF_LOCATION_NAME: "Strathpine"}
        )
    assert result_ok["reason"] == "reconfigure_successful"
    assert entry.unique_id == "ausnz_disaster_watch_qld_strathpine"


async def test_reconfigure_aborts_on_identity_clash(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test reconfigure aborts when another entry already uses the new identity (#6)."""
    mock_config_entry.add_to_hass(hass)
    other = MockConfigEntry(
        domain=DOMAIN,
        data={**RECONFIGURE_INPUT, CONF_LOCATION_NAME: "Brisbane"},
        unique_id="ausnz_disaster_watch_qld_brisbane",
    )
    other.add_to_hass(hass)

    result = await mock_config_entry.start_reconfigure_flow(hass)
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={**RECONFIGURE_INPUT, CONF_LOCATION_NAME: "Brisbane"},
    )
    assert result2["type"] == data_entry_flow.FlowResultType.ABORT
    assert result2["reason"] == "already_configured"
    assert mock_config_entry.unique_id == "ausnz_disaster_watch_qld_city_of_moreton_bay"
    assert mock_config_entry.data[CONF_LOCATION_NAME] == "City of Moreton Bay"


async def test_reconfigure_invalid_config_shows_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test out-of-range values that bypass the selectors give a form error, not an exception (#6)."""
    mock_config_entry.add_to_hass(hass)

    flow = AustralianDisasterWatchConfigFlow()
    flow.hass = hass
    flow._get_reconfigure_entry = lambda: mock_config_entry  # type: ignore[method-assign]
    result = await flow.async_step_reconfigure({**RECONFIGURE_INPUT, CONF_RADIUS: 1000})
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_config"}
    assert mock_config_entry.data[CONF_RADIUS] == 50


async def test_user_steps_invalid_config_show_error(hass: HomeAssistant) -> None:
    """Test the user and location steps return a form error for invalid values."""
    flow = AustralianDisasterWatchConfigFlow()
    flow.hass = hass
    result = await flow.async_step_user(
        {
            CONF_STATE: STATE_QLD,
            CONF_LOCATION_MODE: LOCATION_MODE_HOME,
            CONF_RADIUS: 1000,
            CONF_OVERRIDE_EMERGENCY: True,
            CONF_EXCLUDE_HAZARD_REDUCTION: True,
        }
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_config"}

    flow._user_input = {CONF_STATE: STATE_QLD, CONF_RADIUS: 1000}
    result = await flow.async_step_location(
        {"preset_council": "custom", CONF_LOCATION_NAME: "X", CONF_LATITUDE: -27.0, CONF_LONGITUDE: 153.0}
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_config"}


async def test_custom_location_with_blank_name_uses_stored_name_for_identity(hass: HomeAssistant) -> None:
    """A blank custom location name is stored as "Custom Location" and the unique ID matches it."""
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_STATE: STATE_NSW,
            CONF_LOCATION_MODE: LOCATION_MODE_CUSTOM,
            CONF_RADIUS: 60,
            CONF_OVERRIDE_EMERGENCY: True,
            CONF_EXCLUDE_HAZARD_REDUCTION: True,
        },
    )
    with patch("custom_components.ausnz_disaster_watch.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_LOCATION_NAME: "", CONF_LATITUDE: -33.86, CONF_LONGITUDE: 151.2},
        )
    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_LOCATION_NAME] == "Custom Location"
    assert result["result"].unique_id.endswith("_custom_location")


async def test_reconfigure_explicit_location_source(hass: HomeAssistant) -> None:
    """The reconfigure form asks whether to follow the home zone or keep a fixed point (#19)."""
    hass.config.latitude, hass.config.longitude = -27.2657, 152.9818
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_STATE: STATE_QLD, CONF_LOCATION_MODE: LOCATION_MODE_HOME, CONF_LOCATION_NAME: "Home"},
        unique_id="ausnz_disaster_watch_qld_home",
    )
    entry.add_to_hass(hass)

    # Saving the prefilled home coordinates as a fixed location makes the entry custom
    with patch("custom_components.ausnz_disaster_watch.async_setup_entry", return_value=True):
        result = await entry.start_reconfigure_flow(hass)
        defaults = {str(key): key.default() for key in result["data_schema"].schema}
        assert defaults[CONF_LOCATION_MODE] == LOCATION_MODE_HOME
        await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={**RECONFIGURE_INPUT, CONF_LOCATION_MODE: LOCATION_MODE_CUSTOM}
        )
    assert entry.data[CONF_LOCATION_MODE] == LOCATION_MODE_CUSTOM
    assert entry.data[CONF_LATITUDE] == -27.2657

    # Switching back to the home zone drops the stored point
    with patch("custom_components.ausnz_disaster_watch.async_setup_entry", return_value=True):
        result = await entry.start_reconfigure_flow(hass)
        await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={**RECONFIGURE_INPUT, CONF_LOCATION_NAME: "Home", CONF_LOCATION_MODE: LOCATION_MODE_HOME},
        )
    assert entry.data[CONF_LOCATION_MODE] == LOCATION_MODE_HOME
    assert CONF_LATITUDE not in entry.data
    assert CONF_LONGITUDE not in entry.data
    assert entry.unique_id == "ausnz_disaster_watch_qld_home"
