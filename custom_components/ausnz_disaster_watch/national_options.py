"""Options step for the opt-in national and regional feeds (#37)."""

from __future__ import annotations

from typing import Any, Final

import voluptuous as vol

from homeassistant.config_entries import ConfigFlowResult, OptionsFlowWithReload
from homeassistant.helpers.selector import BooleanSelector

from .const import (
    AU_ONLY_FEED_OPTIONS,
    CONF_ENABLE_AIR_QUALITY,
    CONF_STATE,
    NATIONAL_FEED_OPTIONS,
    STATE_ACT,
    STATE_NSW,
    STATE_NZ,
    STATE_QLD,
)

# State environment agencies with a supported keyless air quality feed
AIR_QUALITY_STATES: Final = (STATE_NSW, STATE_QLD, STATE_ACT)


def national_feed_options(state: str) -> list[str]:
    """Return the opt-in national feed options offered for a jurisdiction."""
    options: list[str] = list(NATIONAL_FEED_OPTIONS)
    if state == STATE_NZ:
        options = [option for option in options if option not in AU_ONLY_FEED_OPTIONS]
    if state not in AIR_QUALITY_STATES:
        options = [option for option in options if option != CONF_ENABLE_AIR_QUALITY]
    return options


class NationalFeedsOptionsFlow(OptionsFlowWithReload):
    """Options step that toggles the national and regional feeds; all default to off."""

    def _save_options(self, updates: dict[str, Any]) -> ConfigFlowResult:
        """Save options without dropping the ones other steps own."""
        return self.async_create_entry(data={**self.config_entry.options, **updates})

    async def async_step_national_feeds(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Toggle tsunami, hotspots, heatwave, UV, state air quality and GDACS feeds."""
        if user_input is not None:
            return self._save_options(user_input)
        current = {**self.config_entry.data, **self.config_entry.options}
        state = str(current.get(CONF_STATE, STATE_QLD)).upper()
        schema = vol.Schema(
            {
                vol.Required(option, default=bool(current.get(option, False))): BooleanSelector()
                for option in national_feed_options(state)
            }
        )
        return self.async_show_form(step_id="national_feeds", data_schema=schema)  # type: ignore[arg-type]
