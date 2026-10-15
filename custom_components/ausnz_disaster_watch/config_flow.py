"""Config flow and Options flow for Australian Disaster Watch."""

from __future__ import annotations

import logging
from typing import Any, Final

from pydantic import ValidationError
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow, OptionsFlowWithReload
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    BooleanSelector,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import (
    CONF_COUNCIL_DASHBOARD_URL,
    CONF_EXCLUDE_HAZARD_REDUCTION,
    CONF_LATITUDE,
    CONF_LOCATION_MODE,
    CONF_LOCATION_NAME,
    CONF_LONGITUDE,
    CONF_OVERRIDE_EMERGENCY,
    CONF_RADIUS,
    CONF_STATE,
    DEFAULT_EXCLUDE_HAZARD_REDUCTION,
    DEFAULT_OVERRIDE_EMERGENCY,
    DEFAULT_RADIUS,
    DOMAIN,
    LOCATION_MODE_CUSTOM,
    LOCATION_MODE_HOME,
    MAX_RADIUS,
    MIN_RADIUS,
    PRESET_COUNCIL_DASHBOARDS,
    STATE_ACT,
    STATE_NSW,
    STATE_NT,
    STATE_NZ,
    STATE_QLD,
    STATE_SA,
    STATE_TAS,
    STATE_VIC,
    STATE_WA,
    SUPPORTED_STATES,
)
from .models import DisasterWatchConfigModel

_LOGGER = logging.getLogger(__name__)


# Simplified Victorian mainland boundary as (latitude, longitude) vertices.
# Derived from the ABS ASGS 2021 state boundary (STE code 2): the NSW border (Murray River
# south bank and the straight line from the Murray's source to Cape Howe) is simplified with
# Douglas-Peucker (about 5 km tolerance) plus extra vertices that keep border towns on the
# correct side (Mildura/Buronga, Echuca/Moama, Wodonga/Albury, Cobram/Barooga). The coast is
# replaced by offshore points and the SA border is the straight line along longitude 140.96.
# It only picks the default state in the setup form, so it does not need survey precision.
VIC_BOUNDARY: Final[tuple[tuple[float, float], ...]] = (
    (-33.9806, 140.9637),
    (-34.0597, 141.0233),
    (-34.1546, 141.4950),
    (-34.2165, 141.5101),
    (-34.0909, 141.7297),
    (-34.1523, 142.1659),
    (-34.3070, 142.2359),
    (-34.3381, 142.3968),
    (-34.5304, 142.3677),
    (-34.5643, 142.4680),
    (-34.7754, 142.5567),
    (-34.7251, 142.6990),
    (-34.6166, 142.6894),
    (-34.5464, 142.7914),
    (-34.6798, 142.8868),
    (-34.6809, 143.1123),
    (-34.7916, 143.3479),
    (-35.0367, 143.3221),
    (-35.1924, 143.3947),
    (-35.2069, 143.5708),
    (-35.3877, 143.6204),
    (-35.5001, 143.9701),
    (-36.1179, 144.7271),
    (-36.0723, 144.9819),
    (-35.9888, 144.9236),
    (-35.8523, 144.9923),
    (-35.8020, 145.5354),
    (-35.9168, 145.6791),
    (-35.9917, 145.8114),
    (-36.0509, 146.3687),
    (-35.9582, 146.5026),
    (-36.1160, 146.9437),
    (-36.1079, 147.0530),
    (-35.9945, 147.1234),
    (-36.0610, 147.3199),
    (-35.9435, 147.4046),
    (-35.9565, 147.7413),
    (-35.9952, 147.9123),
    (-36.1408, 148.0377),
    (-36.3902, 148.0376),
    (-36.5982, 148.2176),
    (-36.8009, 148.1089),
    (-37.5052, 149.9762),
    (-37.6000, 150.3000),
    (-38.2000, 148.5000),
    (-39.0000, 147.0000),
    (-39.3000, 146.3000),
    (-38.8000, 145.0000),
    (-39.0000, 143.5000),
    (-38.6000, 142.0000),
    (-38.3000, 140.9650),
)

# Options that the reconfigure step also edits. Options win over data at runtime, so
# reconfigure has to write them to entry.options too.
RECONFIGURE_OPTION_KEYS: Final = (
    CONF_RADIUS,
    CONF_OVERRIDE_EMERGENCY,
    CONF_EXCLUDE_HAZARD_REDUCTION,
    CONF_COUNCIL_DASHBOARD_URL,
)

# Coordinates closer than this (degrees, about 10 m) count as the same location.
_SAME_LOCATION_TOLERANCE: Final = 0.0001


def point_in_polygon(lat: float, lon: float, polygon: tuple[tuple[float, float], ...]) -> bool:
    """Return True if the point lies inside the polygon (even-odd ray casting)."""
    inside = False
    prev_lat, prev_lon = polygon[-1]
    for vert_lat, vert_lon in polygon:
        if (vert_lat > lat) != (prev_lat > lat):
            crossing_lon = vert_lon + (lat - vert_lat) * (prev_lon - vert_lon) / (prev_lat - vert_lat)
            if lon < crossing_lon:
                inside = not inside
        prev_lat, prev_lon = vert_lat, vert_lon
    return inside


def infer_state_from_coordinates(lat: float, lon: float) -> str:
    """Infer likely Australian or New Zealand state/jurisdiction code from latitude and longitude."""
    # New Zealand
    if -48.0 <= lat <= -34.0 and 165.0 <= lon <= 180.0:
        return STATE_NZ
    # Tasmania
    if lat < -39.5:
        return STATE_TAS
    # Western Australia
    if lon < 129.0:
        return STATE_WA
    # Victoria (south of the Murray River, east of the SA border)
    if point_in_polygon(lat, lon, VIC_BOUNDARY):
        return STATE_VIC
    # Northern Territory
    if -26.0 <= lat < -11.0 and 129.0 <= lon < 138.0:
        return STATE_NT
    # South Australia (south of the NT/QLD border at 26 degrees south)
    if -38.5 <= lat <= -26.0 and 129.0 <= lon < 141.0:
        return STATE_SA
    # ACT check (approximate box around Canberra)
    if -36.0 <= lat <= -35.1 and 148.7 <= lon <= 149.4:
        return STATE_ACT
    # Queensland
    if lat >= -29.0:
        return STATE_QLD
    # Default to NSW
    return STATE_NSW


def build_unique_id(state: str, location_mode: str, location_name: str | None) -> str:
    """Return the config entry unique ID for a state and location."""
    if location_mode == LOCATION_MODE_HOME:
        return f"{DOMAIN}_{state.lower()}_home"
    clean_loc = str(location_name).lower().replace(" ", "_").replace("/", "_")
    return f"{DOMAIN}_{state.lower()}_{clean_loc}"


def build_title(state: str, location_name: str) -> str:
    """Return the config entry title for a state and location."""
    return f"Australia and New Zealand Disaster Watch ({state} - {location_name})"


def is_valid_config(data: dict[str, Any]) -> bool:
    """Return True if the entry data passes the config model validation."""
    try:
        DisasterWatchConfigModel.model_validate(data)
    except ValidationError:
        return False
    return True


class AustralianDisasterWatchConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Australian Disaster Watch."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize config flow."""
        self._user_input: dict[str, Any] = {}

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Handle the initial setup step."""
        errors: dict[str, str] = {}

        # Guess most likely state from Home Assistant coordinates
        default_state = STATE_QLD
        if self.hass.config.latitude and self.hass.config.longitude:
            default_state = infer_state_from_coordinates(
                self.hass.config.latitude,
                self.hass.config.longitude,
            )

        if user_input is not None:
            self._user_input = user_input

            # If user selected custom location, prompt for details in next step
            if user_input.get(CONF_LOCATION_MODE) == LOCATION_MODE_CUSTOM:
                return await self.async_step_location()

            # Otherwise, use Home Zone location
            lat = self.hass.config.latitude or -27.2657
            lon = self.hass.config.longitude or 152.9818
            state = user_input.get(CONF_STATE, default_state)

            council_url: str | None = None
            if state == STATE_QLD:
                # Check if home coordinates are close to Moreton Bay or preset
                council_url = str(PRESET_COUNCIL_DASHBOARDS["moreton_bay"]["url"])

            entry_data = {
                **user_input,
                CONF_LATITUDE: lat,
                CONF_LONGITUDE: lon,
                CONF_LOCATION_NAME: self.hass.config.location_name or "Home",
                CONF_COUNCIL_DASHBOARD_URL: council_url,
            }

            if is_valid_config(entry_data):
                await self.async_set_unique_id(build_unique_id(state, LOCATION_MODE_HOME, None))
                self._abort_if_unique_id_configured()

                title = build_title(state, entry_data[CONF_LOCATION_NAME])
                return self.async_create_entry(title=title, data=entry_data)
            errors["base"] = "invalid_config"

        state_options = [SelectOptionDict(value=s, label=s) for s in SUPPORTED_STATES]

        location_mode_options = [
            SelectOptionDict(
                value=LOCATION_MODE_HOME,
                label=f"Use Home Zone ({self.hass.config.location_name or 'Home'})",
            ),
            SelectOptionDict(
                value=LOCATION_MODE_CUSTOM,
                label="Specify Custom Location (e.g. Moreton Bay / Council / Coordinates)",
            ),
        ]

        data_schema = vol.Schema(
            {
                vol.Required(CONF_STATE, default=default_state): SelectSelector(
                    SelectSelectorConfig(
                        options=state_options,
                        mode=SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Required(CONF_LOCATION_MODE, default=LOCATION_MODE_HOME): SelectSelector(
                    SelectSelectorConfig(
                        options=location_mode_options,
                        mode=SelectSelectorMode.LIST,
                    )
                ),
                vol.Required(CONF_RADIUS, default=DEFAULT_RADIUS): NumberSelector(
                    NumberSelectorConfig(
                        min=MIN_RADIUS,
                        max=MAX_RADIUS,
                        step=5,
                        unit_of_measurement="km",
                        mode=NumberSelectorMode.SLIDER,
                    )
                ),
                vol.Required(CONF_OVERRIDE_EMERGENCY, default=DEFAULT_OVERRIDE_EMERGENCY): BooleanSelector(),
                vol.Required(
                    CONF_EXCLUDE_HAZARD_REDUCTION,
                    default=DEFAULT_EXCLUDE_HAZARD_REDUCTION,
                ): BooleanSelector(),
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,  # type: ignore[arg-type]
            errors=errors,
        )

    async def async_step_location(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Handle step for custom location or preset council selection."""
        errors: dict[str, str] = {}
        state = self._user_input.get(CONF_STATE, STATE_QLD)

        if user_input is not None:
            # Check if preset council was selected
            selected_preset = user_input.get("preset_council")
            lat = user_input.get(CONF_LATITUDE)
            lon = user_input.get(CONF_LONGITUDE)
            location_name = user_input.get(CONF_LOCATION_NAME)
            council_url = user_input.get(CONF_COUNCIL_DASHBOARD_URL)

            if selected_preset and selected_preset in PRESET_COUNCIL_DASHBOARDS:
                preset = PRESET_COUNCIL_DASHBOARDS[selected_preset]
                lat = preset["latitude"]
                lon = preset["longitude"]
                location_name = preset["name"]
                council_url = preset["url"]

            if lat is None or lon is None:
                errors["base"] = "invalid_coordinates"
            else:
                entry_data = {
                    **self._user_input,
                    CONF_LATITUDE: float(lat),
                    CONF_LONGITUDE: float(lon),
                    CONF_LOCATION_NAME: location_name or "Custom Location",
                    CONF_COUNCIL_DASHBOARD_URL: council_url,
                }

                if is_valid_config(entry_data):
                    await self.async_set_unique_id(
                        build_unique_id(state, LOCATION_MODE_CUSTOM, entry_data[CONF_LOCATION_NAME])
                    )
                    self._abort_if_unique_id_configured()

                    title = build_title(state, entry_data[CONF_LOCATION_NAME])
                    return self.async_create_entry(title=title, data=entry_data)
                errors["base"] = "invalid_config"

        # Build preset options filtered by selected state
        preset_options = [SelectOptionDict(value="custom", label="Manual Coordinates / Custom URL")]
        for key, info in PRESET_COUNCIL_DASHBOARDS.items():
            if info["state"] == state:
                preset_options.append(
                    SelectOptionDict(
                        value=key,
                        label=f"{info['name']} (Disaster Dashboard)",
                    )
                )

        # Default custom location to Moreton Bay for QLD
        default_lat = -27.2657 if state == STATE_QLD else (self.hass.config.latitude or -33.8688)
        default_lon = 152.9818 if state == STATE_QLD else (self.hass.config.longitude or 151.2093)
        default_name = "City of Moreton Bay" if state == STATE_QLD else "Custom"
        default_preset = "moreton_bay" if state == STATE_QLD else "custom"
        default_url = "https://disaster.moretonbay.qld.gov.au" if state == STATE_QLD else ""

        schema = vol.Schema(
            {
                vol.Optional("preset_council", default=default_preset): SelectSelector(
                    SelectSelectorConfig(
                        options=preset_options,
                        mode=SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Required(CONF_LOCATION_NAME, default=default_name): TextSelector(
                    TextSelectorConfig(type=TextSelectorType.TEXT)
                ),
                vol.Required(CONF_LATITUDE, default=default_lat): NumberSelector(
                    NumberSelectorConfig(
                        min=-50.0,
                        max=-5.0,
                        step="any",
                        mode=NumberSelectorMode.BOX,
                    )
                ),
                vol.Required(CONF_LONGITUDE, default=default_lon): NumberSelector(
                    NumberSelectorConfig(
                        min=100.0,
                        max=180.0,
                        step="any",
                        mode=NumberSelectorMode.BOX,
                    )
                ),
                vol.Optional(CONF_COUNCIL_DASHBOARD_URL, default=default_url): TextSelector(
                    TextSelectorConfig(type=TextSelectorType.URL)
                ),
            }
        )

        return self.async_show_form(
            step_id="location",
            data_schema=schema,  # type: ignore[arg-type]
            errors=errors,
        )

    async def async_step_reconfigure(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Handle reconfiguration of an existing entry."""
        errors: dict[str, str] = {}
        entry = self._get_reconfigure_entry()

        if user_input is not None:
            lat = user_input.get(CONF_LATITUDE)
            lon = user_input.get(CONF_LONGITUDE)
            parsed_lat: float | None = None
            parsed_lon: float | None = None
            try:
                if lat is not None and lon is not None:
                    parsed_lat = float(lat)
                    parsed_lon = float(lon)
                    if not (-90.0 <= parsed_lat <= 90.0 and -180.0 <= parsed_lon <= 180.0):
                        errors["base"] = "invalid_coordinates"
                else:
                    errors["base"] = "invalid_coordinates"
            except (ValueError, TypeError):
                errors["base"] = "invalid_coordinates"

            if not errors and parsed_lat is not None and parsed_lon is not None:
                updates = {
                    **user_input,
                    CONF_LATITUDE: parsed_lat,
                    CONF_LONGITUDE: parsed_lon,
                    CONF_LOCATION_MODE: self._reconfigured_location_mode(entry, parsed_lat, parsed_lon),
                }
                new_data = {**entry.data, **updates}
                if not is_valid_config(new_data):
                    errors["base"] = "invalid_config"
                else:
                    state = str(new_data.get(CONF_STATE, STATE_QLD))
                    location_name = str(new_data.get(CONF_LOCATION_NAME) or "Home")
                    unique_id = build_unique_id(state, new_data[CONF_LOCATION_MODE], location_name)
                    if unique_id != entry.unique_id:
                        await self.async_set_unique_id(unique_id, raise_on_progress=False)
                        self._abort_if_unique_id_configured()
                    # Options override data at runtime, so keep reconfigured options in sync.
                    options = {
                        **entry.options,
                        **{key: updates[key] for key in RECONFIGURE_OPTION_KEYS if key in updates},
                    }
                    return self.async_update_reload_and_abort(
                        entry,
                        unique_id=unique_id,
                        title=build_title(state, location_name),
                        data_updates=updates,
                        options=options,
                    )

        current = {**entry.data, **entry.options}
        state_options = [SelectOptionDict(value=s, label=s) for s in SUPPORTED_STATES]

        schema = vol.Schema(
            {
                vol.Required(CONF_STATE, default=current.get(CONF_STATE, STATE_QLD)): SelectSelector(
                    SelectSelectorConfig(options=state_options, mode=SelectSelectorMode.DROPDOWN)
                ),
                vol.Required(CONF_LOCATION_NAME, default=current.get(CONF_LOCATION_NAME, "Home")): TextSelector(
                    TextSelectorConfig(type=TextSelectorType.TEXT)
                ),
                vol.Required(CONF_LATITUDE, default=float(current.get(CONF_LATITUDE, -27.2657))): NumberSelector(
                    NumberSelectorConfig(min=-50.0, max=-5.0, step="any", mode=NumberSelectorMode.BOX)
                ),
                vol.Required(CONF_LONGITUDE, default=float(current.get(CONF_LONGITUDE, 152.9818))): NumberSelector(
                    NumberSelectorConfig(min=100.0, max=180.0, step="any", mode=NumberSelectorMode.BOX)
                ),
                vol.Required(CONF_RADIUS, default=int(current.get(CONF_RADIUS, DEFAULT_RADIUS))): NumberSelector(
                    NumberSelectorConfig(
                        min=MIN_RADIUS,
                        max=MAX_RADIUS,
                        step=5,
                        unit_of_measurement="km",
                        mode=NumberSelectorMode.SLIDER,
                    )
                ),
                vol.Required(
                    CONF_OVERRIDE_EMERGENCY,
                    default=bool(current.get(CONF_OVERRIDE_EMERGENCY, DEFAULT_OVERRIDE_EMERGENCY)),
                ): BooleanSelector(),
                vol.Required(
                    CONF_EXCLUDE_HAZARD_REDUCTION,
                    default=bool(current.get(CONF_EXCLUDE_HAZARD_REDUCTION, DEFAULT_EXCLUDE_HAZARD_REDUCTION)),
                ): BooleanSelector(),
                vol.Optional(
                    CONF_COUNCIL_DASHBOARD_URL,
                    default=current.get(CONF_COUNCIL_DASHBOARD_URL, "") or "",
                ): TextSelector(TextSelectorConfig(type=TextSelectorType.URL)),
            }
        )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=schema,  # type: ignore[arg-type]
            errors=errors,
        )

    @staticmethod
    def _reconfigured_location_mode(entry: ConfigEntry, lat: float, lon: float) -> str:
        """Return the location mode after reconfigure.

        A home-zone entry stays in home mode only while its coordinates are unchanged;
        moving the location makes it a custom location with its own unique ID.
        """
        mode = entry.data.get(CONF_LOCATION_MODE, LOCATION_MODE_HOME)
        if mode != LOCATION_MODE_HOME:
            return str(mode)
        old_lat = entry.data.get(CONF_LATITUDE)
        old_lon = entry.data.get(CONF_LONGITUDE)
        if (
            old_lat is not None
            and old_lon is not None
            and abs(float(old_lat) - lat) < _SAME_LOCATION_TOLERANCE
            and abs(float(old_lon) - lon) < _SAME_LOCATION_TOLERANCE
        ):
            return LOCATION_MODE_HOME
        return LOCATION_MODE_CUSTOM

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> OptionsFlow:
        """Create the options flow."""
        return AustralianDisasterWatchOptionsFlowHandler()


class AustralianDisasterWatchOptionsFlowHandler(OptionsFlowWithReload):
    """Handle options flow for Australia and New Zealand Disaster Watch."""

    async def async_step_init(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current_config = {
            **self.config_entry.data,
            **self.config_entry.options,
        }

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_RADIUS,
                    default=current_config.get(CONF_RADIUS, DEFAULT_RADIUS),
                ): NumberSelector(
                    NumberSelectorConfig(
                        min=MIN_RADIUS,
                        max=MAX_RADIUS,
                        step=5,
                        unit_of_measurement="km",
                        mode=NumberSelectorMode.SLIDER,
                    )
                ),
                vol.Required(
                    CONF_OVERRIDE_EMERGENCY,
                    default=current_config.get(CONF_OVERRIDE_EMERGENCY, DEFAULT_OVERRIDE_EMERGENCY),
                ): BooleanSelector(),
                vol.Required(
                    CONF_EXCLUDE_HAZARD_REDUCTION,
                    default=current_config.get(CONF_EXCLUDE_HAZARD_REDUCTION, DEFAULT_EXCLUDE_HAZARD_REDUCTION),
                ): BooleanSelector(),
                vol.Optional(
                    CONF_COUNCIL_DASHBOARD_URL,
                    default=current_config.get(CONF_COUNCIL_DASHBOARD_URL, "") or "",
                ): TextSelector(TextSelectorConfig(type=TextSelectorType.URL)),
            }
        )

        return self.async_show_form(
            step_id="init",
            data_schema=schema,  # type: ignore[arg-type]
        )


AusNZDisasterWatchConfigFlow = AustralianDisasterWatchConfigFlow
AusNZDisasterWatchOptionsFlowHandler = AustralianDisasterWatchOptionsFlowHandler
EmergencyHazardsConfigFlow = AustralianDisasterWatchConfigFlow
EmergencyHazardsOptionsFlowHandler = AustralianDisasterWatchOptionsFlowHandler
