"""Options step for the road and flood camera networks (#70)."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlowResult, OptionsFlowWithReload
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import (
    CONF_CAMERA_MAX,
    CONF_CAMERA_NETWORKS,
    CONF_CAMERA_RADIUS,
    CONF_STATE,
    DEFAULT_CAMERA_MAX,
    DEFAULT_CAMERA_RADIUS,
    MAX_CAMERA_MAX,
    MAX_RADIUS,
    STATE_QLD,
)
from .providers.cameras import camera_networks_for_state


class CameraOptionsFlow(OptionsFlowWithReload):
    """Options step that picks camera networks, the camera radius and the entity cap; no network by default."""

    @property
    def _camera_networks(self) -> tuple[str, ...]:
        """Return the camera networks offered for this entry's jurisdiction."""
        current = {**self.config_entry.data, **self.config_entry.options}
        return camera_networks_for_state(str(current.get(CONF_STATE, STATE_QLD)))

    async def async_step_cameras(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Choose the camera networks near this entry, how far to look and how many cameras to add."""
        if user_input is not None:
            updates = {
                CONF_CAMERA_NETWORKS: list(user_input.get(CONF_CAMERA_NETWORKS, [])),
                CONF_CAMERA_RADIUS: int(user_input[CONF_CAMERA_RADIUS]),
                CONF_CAMERA_MAX: int(user_input[CONF_CAMERA_MAX]),
            }
            return self.async_create_entry(data={**self.config_entry.options, **updates})
        current = {**self.config_entry.data, **self.config_entry.options}
        chosen = [n for n in current.get(CONF_CAMERA_NETWORKS) or [] if n in self._camera_networks]
        schema = vol.Schema(
            {
                vol.Optional(CONF_CAMERA_NETWORKS, default=chosen): SelectSelector(
                    SelectSelectorConfig(
                        options=list(self._camera_networks),
                        multiple=True,
                        mode=SelectSelectorMode.LIST,
                        translation_key=CONF_CAMERA_NETWORKS,
                    )
                ),
                vol.Required(
                    CONF_CAMERA_RADIUS, default=current.get(CONF_CAMERA_RADIUS, DEFAULT_CAMERA_RADIUS)
                ): NumberSelector(
                    NumberSelectorConfig(
                        min=1, max=MAX_RADIUS, step=1, mode=NumberSelectorMode.BOX, unit_of_measurement="km"
                    )
                ),
                vol.Required(CONF_CAMERA_MAX, default=current.get(CONF_CAMERA_MAX, DEFAULT_CAMERA_MAX)): NumberSelector(
                    NumberSelectorConfig(min=1, max=MAX_CAMERA_MAX, step=1, mode=NumberSelectorMode.BOX)
                ),
            }
        )
        return self.async_show_form(step_id="cameras", data_schema=schema)  # type: ignore[arg-type]
