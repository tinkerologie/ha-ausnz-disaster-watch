"""Options step for opt-in hazard feeds (Geoscience Australia earthquakes, #23)."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlowResult
from homeassistant.helpers.selector import BooleanSelector

from .const import CONF_INCLUDE_EARTHQUAKES, CONF_STATE, DEFAULT_INCLUDE_EARTHQUAKES, STATE_NZ
from .forecast_options import ForecastOptionsFlow


class HazardOptionsFlow(ForecastOptionsFlow):
    """Options steps for optional hazard feeds."""

    @property
    def _offers_earthquakes(self) -> bool:
        """Return True for Australian entries; New Zealand entries already get GeoNet quakes."""
        current = {**self.config_entry.data, **self.config_entry.options}
        return str(current.get(CONF_STATE, "")).upper() != STATE_NZ

    async def async_step_earthquakes(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Turn Geoscience Australia earthquakes on or off."""
        if user_input is not None:
            return self._save(user_input)
        current = {**self.config_entry.data, **self.config_entry.options}
        schema = vol.Schema(
            {
                vol.Required(
                    CONF_INCLUDE_EARTHQUAKES,
                    default=current.get(CONF_INCLUDE_EARTHQUAKES, DEFAULT_INCLUDE_EARTHQUAKES),
                ): BooleanSelector(),
            }
        )
        return self.async_show_form(step_id="earthquakes", data_schema=schema)
