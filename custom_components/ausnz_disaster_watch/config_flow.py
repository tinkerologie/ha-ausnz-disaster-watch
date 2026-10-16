"""Config flow and Options flow for Australian Disaster Watch."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Final

from pydantic import ValidationError
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
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
from homeassistant.util import dt as dt_util

from .const import (
    CONF_COUNCIL_DASHBOARD_URL,
    CONF_EXCLUDE_HAZARD_REDUCTION,
    CONF_EXTRA_OUTAGE_FEEDS,
    CONF_INCLUDE_PLANNED_OUTAGES,
    CONF_INCLUDE_ROADWORKS,
    CONF_LATITUDE,
    CONF_LOCATION_MODE,
    CONF_LOCATION_NAME,
    CONF_LONGITUDE,
    CONF_OVERRIDE_EMERGENCY,
    CONF_RADIUS,
    CONF_RIVER_GAUGES,
    CONF_STATE,
    CONF_VIC_API_KEY,
    DEFAULT_EXCLUDE_HAZARD_REDUCTION,
    DEFAULT_EXTRA_OUTAGE_FEEDS,
    DEFAULT_INCLUDE_PLANNED_OUTAGES,
    DEFAULT_INCLUDE_ROADWORKS,
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
from .coordinator import nearest_council_dashboard
from .council_registry import councils_for_state, usable_url
from .hazard_options import HazardOptionsFlow
from .models import DisasterWatchConfigModel
from .national_options import NationalFeedsOptionsFlow
from .providers import POWER_OUTAGE_SOURCES
from .rivers import (
    RIVER_DISCOVERY_TIMEOUT,
    STATE_RIVER_SOURCES,
    GaugeReading,
    GaugeSite,
    RiverSourceError,
    async_discover_gauges,
    haversine_km,
    sites_from_options,
)

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
    MINOR_VERSION = 2

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

            # Otherwise follow the Home Assistant home location. Coordinates are not stored:
            # the coordinator reads the home location at every refresh (#19).
            state = user_input.get(CONF_STATE, default_state)

            # Nearest preset council dashboard near home, if any (changeable in the options)
            council_url = nearest_council_dashboard(state, self.hass.config.latitude, self.hass.config.longitude)

            entry_data = {
                **user_input,
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

        # Councils of the selected state from the generated registry, sorted by name (#32)
        preset_options = [SelectOptionDict(value="custom", label="Manual Coordinates / Custom URL")]
        for key, info in councils_for_state(state):
            label = info["name"] if usable_url(info) else f"{info['name']} (no readable dashboard)"
            preset_options.append(SelectOptionDict(value=key, label=label))

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
                    CONF_LOCATION_MODE: self._chosen_location_mode(
                        entry, user_input.get(CONF_LOCATION_MODE), parsed_lat, parsed_lon
                    ),
                }
                if updates[CONF_LOCATION_MODE] == LOCATION_MODE_HOME:
                    # Home-zone entries follow the Home Assistant home location; no stored point (#19)
                    updates.pop(CONF_LATITUDE)
                    updates.pop(CONF_LONGITUDE)
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
                    if new_data[CONF_LOCATION_MODE] == LOCATION_MODE_HOME:
                        # data_updates would merge into the stored data and keep an old fixed point
                        new_data.pop(CONF_LATITUDE, None)
                        new_data.pop(CONF_LONGITUDE, None)
                    return self.async_update_reload_and_abort(
                        entry,
                        unique_id=unique_id,
                        title=build_title(state, location_name),
                        data=new_data,
                        options=options,
                    )

        current = {**entry.data, **entry.options}
        if current.get(CONF_LOCATION_MODE, LOCATION_MODE_HOME) == LOCATION_MODE_HOME:
            # Home-zone entries monitor the current home location, not stored coordinates
            current[CONF_LATITUDE] = self.hass.config.latitude
            current[CONF_LONGITUDE] = self.hass.config.longitude
        state_options = [SelectOptionDict(value=s, label=s) for s in SUPPORTED_STATES]
        location_mode_options = [
            SelectOptionDict(
                value=LOCATION_MODE_HOME,
                label=f"Follow Home Zone ({self.hass.config.location_name or 'Home'})",
            ),
            SelectOptionDict(value=LOCATION_MODE_CUSTOM, label="Fixed location (the coordinates below)"),
        ]

        schema = vol.Schema(
            {
                vol.Required(CONF_STATE, default=current.get(CONF_STATE, STATE_QLD)): SelectSelector(
                    SelectSelectorConfig(options=state_options, mode=SelectSelectorMode.DROPDOWN)
                ),
                vol.Required(
                    CONF_LOCATION_MODE, default=current.get(CONF_LOCATION_MODE, LOCATION_MODE_HOME)
                ): SelectSelector(SelectSelectorConfig(options=location_mode_options, mode=SelectSelectorMode.LIST)),
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

    def _chosen_location_mode(self, entry: ConfigEntry, chosen: str | None, lat: float, lon: float) -> str:
        """Return the location mode after reconfigure.

        Choosing "fixed location" always fixes the submitted point, and choosing the home
        zone switches a fixed entry back to following home. A home-zone entry left on the
        home zone becomes a fixed location if its coordinates were changed, so edited
        coordinates are never silently ignored.
        """
        current = entry.data.get(CONF_LOCATION_MODE, LOCATION_MODE_HOME)
        if chosen == LOCATION_MODE_CUSTOM:
            return LOCATION_MODE_CUSTOM
        if chosen == LOCATION_MODE_HOME and current != LOCATION_MODE_HOME:
            return LOCATION_MODE_HOME
        return self._reconfigured_location_mode(entry, lat, lon)

    def _reconfigured_location_mode(self, entry: ConfigEntry, lat: float, lon: float) -> str:
        """Return the location mode after reconfigure.

        A home-zone entry stays in home mode only while the submitted coordinates are the
        Home Assistant home location the form showed (coordinates stored by older versions
        are ignored); moving the location makes it a custom location with its own unique ID.
        """
        mode = entry.data.get(CONF_LOCATION_MODE, LOCATION_MODE_HOME)
        if mode != LOCATION_MODE_HOME:
            return str(mode)
        old_lat = self.hass.config.latitude
        old_lon = self.hass.config.longitude
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


def gauge_label(reading: GaugeReading, latitude: float, longitude: float) -> str:
    """Return the options-flow label of a discovered gauge: name, distance and current level."""
    site = reading.site
    distance = haversine_km(latitude, longitude, site.latitude, site.longitude)
    return f"{site.name} ({distance:.1f} km, {reading.level_m:.2f} m)"


def gauge_field_names(sites: list[GaugeSite]) -> list[str]:
    """Return one form field name per gauge for the alert-level form.

    Field names are shown as labels when they have no translation, so they are the gauge
    names; a repeated name gets its site ID appended so every field stays unique.
    """
    names = [site.name for site in sites]
    return [f"{site.name} ({site.site_id})" if names.count(site.name) > 1 else site.name for site in sites]


def road_option_fields(current_config: dict[str, Any]) -> dict[Any, Any]:
    """Return the road feed option fields (#29) for the entry's state.

    Planned roadworks and events are off by default (ACT has no road feed, and the NZTA feed
    never lists planned works); the
    optional DTP open data key is offered for Victoria only.
    """
    state = str(current_config.get(CONF_STATE, STATE_QLD)).upper()
    fields: dict[Any, Any] = {}
    if state not in (STATE_ACT, STATE_NZ):
        fields[
            vol.Required(
                CONF_INCLUDE_ROADWORKS,
                default=current_config.get(CONF_INCLUDE_ROADWORKS, DEFAULT_INCLUDE_ROADWORKS),
            )
        ] = BooleanSelector()
    if state == STATE_VIC:
        fields[
            vol.Optional(CONF_VIC_API_KEY, description={"suggested_value": current_config.get(CONF_VIC_API_KEY)})
        ] = TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD))
    return fields


def power_option_fields(current_config: dict[str, Any]) -> dict[Any, Any]:
    """Return the power outage option fields (#36) for the entry's state.

    Only states with a distributor outage feed get the page; the extra feeds toggle only
    where an opt-in feed exists (Western Power, Powerco, Unison).
    """
    state = str(current_config.get(CONF_STATE, STATE_QLD)).upper()
    sources = POWER_OUTAGE_SOURCES.get(state, ())
    fields: dict[Any, Any] = {}
    if not sources:
        return fields
    fields[
        vol.Required(
            CONF_INCLUDE_PLANNED_OUTAGES,
            default=current_config.get(CONF_INCLUDE_PLANNED_OUTAGES, DEFAULT_INCLUDE_PLANNED_OUTAGES),
        )
    ] = BooleanSelector()
    if any(source.opt_in for source in sources):
        fields[
            vol.Required(
                CONF_EXTRA_OUTAGE_FEEDS,
                default=current_config.get(CONF_EXTRA_OUTAGE_FEEDS, DEFAULT_EXTRA_OUTAGE_FEEDS),
            )
        ] = BooleanSelector()
    return fields


def clean_road_options(options: dict[str, Any], user_input: dict[str, Any]) -> dict[str, Any]:
    """Merge the road step into the saved options; a cleared or blank VIC key removes the key.

    The key lives only in the options, so removing it there means "no key".
    """
    cleaned = {**options, **user_input}
    if key := str(user_input.get(CONF_VIC_API_KEY) or "").strip():
        cleaned[CONF_VIC_API_KEY] = key
    else:
        cleaned.pop(CONF_VIC_API_KEY, None)
    return cleaned


class AustralianDisasterWatchOptionsFlowHandler(HazardOptionsFlow, NationalFeedsOptionsFlow):
    """Handle options flow for Australia and New Zealand Disaster Watch."""

    def __init__(self) -> None:
        """Initialize the options flow."""
        super().__init__()
        # Gauges offered on the river gauge form, by GaugeSite.key
        self._discovered: dict[str, GaugeSite] = {}
        # Gauges ticked on the river gauge form, waiting for their alert levels
        self._chosen: list[GaugeSite] = []

    async def async_step_init(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Show the options menu.

        River point edit/remove only appear once a point exists; the river gauge picker only
        where a gauge service covers the state (#31).
        """
        menu = ["settings", "forecasts", "national_feeds", "add_river_point"]
        if self._offers_earthquakes:
            menu.insert(2, "earthquakes")
        if road_option_fields({**self.config_entry.data, **self.config_entry.options}):
            menu.insert(1, "roads")
        if power_option_fields({**self.config_entry.data, **self.config_entry.options}):
            menu.insert(menu.index("roads") + 1 if "roads" in menu else 1, "power_outages")
        if self._points:
            menu += ["edit_river_point", "remove_river_point"]
        state = str({**self.config_entry.data, **self.config_entry.options}.get(CONF_STATE, "")).upper()
        if state in STATE_RIVER_SOURCES:
            menu.append("river_gauges")
        return self.async_show_menu(step_id="init", menu_options=menu)

    async def async_step_settings(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Manage the monitoring options."""
        if user_input is not None:
            return self._save(user_input)

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
            step_id="settings",
            data_schema=schema,  # type: ignore[arg-type]
        )

    async def async_step_river_gauges(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Pick river and creek gauges near the location; none are selected by default (#31)."""
        selected = sites_from_options(self.config_entry.options.get(CONF_RIVER_GAUGES))

        if user_input is not None:
            levels = {site.key: site.alert_level_m for site in selected}
            known: dict[str, GaugeSite] = {**self._discovered, **{site.key: site for site in selected}}
            # The selector only accepts listed keys, all of which are known
            keys = user_input.get(CONF_RIVER_GAUGES, [])
            self._chosen = [known[key].with_alert_level(levels.get(key)) for key in keys]
            if not self._chosen:
                return self._save({CONF_RIVER_GAUGES: []})
            return await self.async_step_river_alert_levels()

        config = {**self.config_entry.data, **self.config_entry.options}
        # Same point as the coordinator: home-mode entries follow the home location (#19)
        home = (self.hass.config.latitude, self.hass.config.longitude)
        stored = (config.get(CONF_LATITUDE), config.get(CONF_LONGITUDE))
        candidates = (home, stored) if config.get(CONF_LOCATION_MODE) == LOCATION_MODE_HOME else (stored, home)
        latitude, longitude = next((float(la), float(lo)) for la, lo in candidates if la is not None and lo is not None)
        errors: dict[str, str] = {}
        labels = {site.key: f"{site.name} (selected)" for site in selected}
        try:
            # Bound the wait: one hanging council server must not hold the form for minutes
            async with asyncio.timeout(RIVER_DISCOVERY_TIMEOUT.total_seconds()):
                discovered = await async_discover_gauges(
                    async_get_clientsession(self.hass),
                    state=str(config.get(CONF_STATE, STATE_QLD)),
                    latitude=latitude,
                    longitude=longitude,
                    radius_km=float(config.get(CONF_RADIUS, DEFAULT_RADIUS)),
                    now=dt_util.utcnow(),
                )
        except (RiverSourceError, TimeoutError) as err:
            _LOGGER.debug("River gauge discovery failed: %r", err)
            errors["base"] = "rivers_unavailable"
            discovered = []
        self._discovered = {reading.site.key: reading.site for reading in discovered}
        for reading in discovered:
            labels[reading.site.key] = gauge_label(reading, latitude, longitude)
        if not labels and not errors:
            errors["base"] = "no_river_gauges"

        schema = vol.Schema(
            {
                vol.Optional(CONF_RIVER_GAUGES, default=[site.key for site in selected]): SelectSelector(
                    SelectSelectorConfig(
                        options=[SelectOptionDict(value=key, label=label) for key, label in labels.items()],
                        multiple=True,
                        mode=SelectSelectorMode.LIST,
                    )
                ),
            }
        )
        return self.async_show_form(
            step_id="river_gauges",
            data_schema=schema,  # type: ignore[arg-type]
            errors=errors,
        )

    async def async_step_river_alert_levels(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Set an optional alert level (m) per chosen gauge; blank means no alert sensor (#31)."""
        fields = gauge_field_names(self._chosen)
        if user_input is not None:
            gauges = [
                # A cleared box can arrive as a missing key or an empty string
                site.with_alert_level(None if (level := user_input.get(field)) in (None, "") else float(level))
                for site, field in zip(self._chosen, fields, strict=True)
            ]
            return self._save({CONF_RIVER_GAUGES: [site.as_dict() for site in gauges]})

        schema: dict[Any, Any] = {}
        for site, field in zip(self._chosen, fields, strict=True):
            suggested = {"suggested_value": site.alert_level_m} if site.alert_level_m is not None else None
            schema[vol.Optional(field, description=suggested)] = NumberSelector(
                NumberSelectorConfig(
                    min=-100, max=1000, step="any", unit_of_measurement="m", mode=NumberSelectorMode.BOX
                )
            )
        return self.async_show_form(
            step_id="river_alert_levels",
            data_schema=vol.Schema(schema),  # type: ignore[arg-type]
        )

    async def async_step_power_outages(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Manage the power outage options (#36)."""
        if user_input is not None:
            return self._save(user_input)
        current_config = {**self.config_entry.data, **self.config_entry.options}
        return self.async_show_form(
            step_id="power_outages",
            data_schema=vol.Schema(power_option_fields(current_config)),  # type: ignore[arg-type]
        )

    async def async_step_roads(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Manage the statewide road feed options (#29)."""
        if user_input is not None:
            return self.async_create_entry(data=clean_road_options(dict(self.config_entry.options), user_input))
        current_config = {**self.config_entry.data, **self.config_entry.options}
        return self.async_show_form(
            step_id="roads",
            data_schema=vol.Schema(road_option_fields(current_config)),  # type: ignore[arg-type]
        )


AusNZDisasterWatchConfigFlow = AustralianDisasterWatchConfigFlow
AusNZDisasterWatchOptionsFlowHandler = AustralianDisasterWatchOptionsFlowHandler
EmergencyHazardsConfigFlow = AustralianDisasterWatchConfigFlow
EmergencyHazardsOptionsFlowHandler = AustralianDisasterWatchOptionsFlowHandler
