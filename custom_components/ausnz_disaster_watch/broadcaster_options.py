"""Options step for the opt-in emergency broadcaster (#73)."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlowResult, OptionsFlowWithReload
from homeassistant.helpers.selector import SelectOptionDict, SelectSelector, SelectSelectorConfig, SelectSelectorMode

from .broadcaster import (
    BROADCASTER_NEAREST,
    BROADCASTER_OFF,
    async_load_broadcasters,
    broadcaster_option,
    stations_by_distance,
)
from .const import (
    CONF_EMERGENCY_BROADCASTER,
    CONF_LATITUDE,
    CONF_LOCATION_MODE,
    CONF_LONGITUDE,
    CONF_STATE,
    LOCATION_MODE_HOME,
    STATE_QLD,
)


class BroadcasterOptionsFlow(OptionsFlowWithReload):
    """Options step that turns the emergency broadcaster on and picks its station."""

    def _monitored_point(self) -> tuple[float, float]:
        """Return the entry's monitored point (the home location for home-zone entries)."""
        current = {**self.config_entry.data, **self.config_entry.options}
        home = (self.hass.config.latitude, self.hass.config.longitude)
        stored = (current.get(CONF_LATITUDE), current.get(CONF_LONGITUDE))
        if current.get(CONF_LOCATION_MODE, LOCATION_MODE_HOME) == LOCATION_MODE_HOME or None in stored:
            return home
        return float(stored[0]), float(stored[1])  # type: ignore[arg-type]

    async def async_step_emergency_broadcaster(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Choose off, the nearest station, or a station of the entry's country."""
        if user_input is not None:
            return self.async_create_entry(data={**self.config_entry.options, **user_input})
        state = str({**self.config_entry.data, **self.config_entry.options}.get(CONF_STATE, STATE_QLD))
        latitude, longitude = self._monitored_point()
        ranked = stations_by_distance(await async_load_broadcasters(self.hass), state, latitude, longitude)
        nearest = ranked[0][0].name  # the table has stations for both countries
        options = [
            # Translated labels; the station labels below are proper names and stay as they are
            SelectOptionDict(value=BROADCASTER_OFF, label=BROADCASTER_OFF),
            SelectOptionDict(value=BROADCASTER_NEAREST, label=BROADCASTER_NEAREST),
            *(
                SelectOptionDict(value=station.key, label=f"{station.name} ({station.state}, {distance:.0f} km)")
                for station, distance in ranked
            ),
        ]
        current = broadcaster_option(self.config_entry)
        if current not in {option["value"] for option in options}:
            current = BROADCASTER_NEAREST  # a station no longer in the table falls back to the nearest
        schema = vol.Schema(
            {
                vol.Required(CONF_EMERGENCY_BROADCASTER, default=current): SelectSelector(
                    SelectSelectorConfig(
                        options=options,
                        mode=SelectSelectorMode.DROPDOWN,
                        translation_key=CONF_EMERGENCY_BROADCASTER,
                    )
                ),
            }
        )
        return self.async_show_form(
            step_id="emergency_broadcaster",
            data_schema=schema,  # type: ignore[arg-type]
            description_placeholders={"nearest": nearest},
        )
