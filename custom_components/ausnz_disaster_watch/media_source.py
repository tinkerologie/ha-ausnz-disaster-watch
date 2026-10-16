"""Media source for the emergency broadcaster (#73).

Each config entry with the emergency broadcaster turned on appears in the media browser
under the integration. ``media-source://ausnz_disaster_watch/emergency_broadcaster/<entry_id>``
resolves, at play time, to the entry's current station stream, so an automation using it
keeps working when the station changes (the home moved, or another station was chosen).
Home Assistant only hands the HTTPS stream URL to the media player; it never proxies audio.
"""

from __future__ import annotations

from typing import override

from homeassistant.components.media_player.const import MediaClass, MediaType
from homeassistant.components.media_player.errors import BrowseError
from homeassistant.components.media_source import (
    BrowseMediaSource,
    MediaSource,
    MediaSourceItem,
    PlayMedia,
    Unresolvable,
)
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.core import HomeAssistant

from .broadcaster import (
    MEDIA_PREFIX,
    BroadcasterChoice,
    async_load_broadcasters,
    broadcaster_enabled,
    broadcaster_option,
    choose_broadcaster,
)
from .const import DEFAULT_NAME, DOMAIN


async def async_get_media_source(hass: HomeAssistant) -> EmergencyBroadcasterMediaSource:
    """Set up the emergency broadcaster media source."""
    return EmergencyBroadcasterMediaSource(hass)


class EmergencyBroadcasterMediaSource(MediaSource):
    """Expose each entry's emergency broadcaster as a playable stream."""

    name = DEFAULT_NAME

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialise the media source."""
        super().__init__(DOMAIN)
        self.hass = hass

    def _entries(self) -> list[ConfigEntry]:
        """Return the loaded entries with the broadcaster turned on."""
        return [entry for entry in self.hass.config_entries.async_loaded_entries(DOMAIN) if broadcaster_enabled(entry)]

    async def _choice(self, entry: ConfigEntry) -> BroadcasterChoice | None:
        coordinator = entry.runtime_data
        return choose_broadcaster(
            await async_load_broadcasters(self.hass),
            broadcaster_option(entry),
            coordinator.state_code,
            coordinator.latitude,
            coordinator.longitude,
        )

    def _entry_for(self, identifier: str) -> ConfigEntry | None:
        """Return the loaded, enabled entry an identifier names, or None."""
        prefix, _, entry_id = identifier.partition("/")
        if prefix != MEDIA_PREFIX:
            return None
        entry = self.hass.config_entries.async_get_entry(entry_id)
        if entry is None or entry.domain != DOMAIN or entry.state is not ConfigEntryState.LOADED:
            return None
        return entry if broadcaster_enabled(entry) else None

    def _item(self, entry: ConfigEntry, choice: BroadcasterChoice) -> BrowseMediaSource:
        return BrowseMediaSource(
            domain=DOMAIN,
            identifier=f"{MEDIA_PREFIX}/{entry.entry_id}",
            media_class=MediaClass.CHANNEL,
            media_content_type=MediaType.MUSIC,
            title=f"Emergency broadcaster: {choice.station.name} ({entry.title})",
            can_play=True,
            can_expand=False,
        )

    @override
    async def async_resolve_media(self, item: MediaSourceItem) -> PlayMedia:
        """Resolve an entry's emergency broadcaster to its current stream."""
        entry = self._entry_for(item.identifier or "")
        choice = await self._choice(entry) if entry is not None else None
        if choice is None:
            raise Unresolvable(
                translation_domain=DOMAIN,
                translation_key="broadcaster_unavailable",
                translation_placeholders={"identifier": item.identifier or ""},
            )
        return PlayMedia(choice.station.stream_url, choice.station.mime_type)

    @override
    async def async_browse_media(self, item: MediaSourceItem) -> BrowseMediaSource:
        """List each entry's emergency broadcaster, or show one of them."""
        if item.identifier:
            entry = self._entry_for(item.identifier)
            if entry is None or (choice := await self._choice(entry)) is None:
                raise BrowseError(
                    translation_domain=DOMAIN,
                    translation_key="broadcaster_unavailable",
                    translation_placeholders={"identifier": item.identifier},
                )
            return self._item(entry, choice)
        children = [
            self._item(entry, choice) for entry in self._entries() if (choice := await self._choice(entry)) is not None
        ]
        return BrowseMediaSource(
            domain=DOMAIN,
            identifier=None,
            media_class=MediaClass.DIRECTORY,
            media_content_type=MediaType.MUSIC,
            title=DEFAULT_NAME,
            can_play=False,
            can_expand=True,
            children_media_class=MediaClass.CHANNEL,
            children=children,
        )
