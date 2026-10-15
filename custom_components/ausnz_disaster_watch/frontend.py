"""Serve the Lovelace dashboard card bundle and keep its resource registration tidy.

The integration owns exactly one Lovelace resource, the card suite bundle
``/ausnz_disaster_watch/ausnz-disaster-card.js``. Resources left behind by older
versions (the ``aus-disaster-card.js`` stub) and duplicates of the bundle are removed,
and the resource is removed again when the last config entry is deleted (#22).
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Final

from homeassistant.components.frontend import add_extra_js_url, remove_extra_js_url
from homeassistant.components.http import StaticPathConfig  # pyright: ignore[reportPrivateImportUsage]
from homeassistant.components.lovelace.const import LOVELACE_DATA
from homeassistant.components.lovelace.resources import ResourceStorageCollection
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.start import async_at_started
from homeassistant.loader import async_get_integration
from homeassistant.util.hass_dict import HassKey

from .const import DOMAIN

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

FRONTEND_URL_BASE: Final = f"/{DOMAIN}"
FRONTEND_PATH: Final = Path(__file__).parent / "frontend"
CARD_FILES: Final = ("ausnz-disaster-card.js",)
# Resources registered by earlier versions that must not survive an upgrade.
LEGACY_CARD_FILES: Final = ("aus-disaster-card.js",)
CARD_URLS: Final = tuple(f"{FRONTEND_URL_BASE}/{filename}" for filename in CARD_FILES)
LEGACY_CARD_URLS: Final = tuple(f"{FRONTEND_URL_BASE}/{filename}" for filename in LEGACY_CARD_FILES)

_REGISTERED: HassKey[bool] = HassKey(f"{DOMAIN}_frontend_registered")
_STATIC_REGISTERED: HassKey[bool] = HassKey(f"{DOMAIN}_frontend_static_registered")
_LOCK: HassKey[asyncio.Lock] = HassKey(f"{DOMAIN}_frontend_lock")
_EXTRA_JS_URLS: HassKey[list[str]] = HassKey(f"{DOMAIN}_frontend_extra_js_urls")


def _base_url(url: str) -> str:
    """Return a resource URL without its query string."""
    return url.partition("?")[0]


def _frontend_digest(path: Path) -> str:
    """Short content hash of frontend assets for cache busting."""
    if not path.is_dir():
        return "none"
    hasher = hashlib.sha256()
    has_files = False
    for file_path in sorted(path.rglob("*.js")):
        if file_path.is_file():
            has_files = True
            hasher.update(file_path.relative_to(path).as_posix().encode())
            hasher.update(file_path.read_bytes())
    if not has_files:
        return "none"
    return hasher.hexdigest()[:8]


def _frontend_assets_info(path: Path, files: tuple[str, ...]) -> tuple[str, list[str]]:
    """Return content hash and existing entry filenames off event loop."""
    digest = _frontend_digest(path)
    existing = [filename for filename in files if (path / filename).is_file()]
    return digest, existing


def _lock(hass: HomeAssistant) -> asyncio.Lock:
    """Return the lock that serialises registration and cleanup."""
    if (lock := hass.data.get(_LOCK)) is None:
        lock = hass.data[_LOCK] = asyncio.Lock()
    return lock


async def async_register_frontend(hass: HomeAssistant) -> None:
    """Serve the card bundle and register it as a Lovelace resource."""
    if not {"http", "frontend"} <= hass.config.components:
        if hass.is_running:
            _LOGGER.debug("http/frontend not loaded; card bundle registration skipped")
            return

        async def _async_register_on_start(_: HomeAssistant) -> None:
            # The entry may have been removed while Home Assistant was starting.
            if hass.config_entries.async_entries(DOMAIN):
                await async_register_frontend(hass)

        async_at_started(hass, _async_register_on_start)
        return

    async with _lock(hass):
        if hass.data.get(_REGISTERED):
            return
        try:
            integration = await async_get_integration(hass, DOMAIN)
            if not hass.data.get(_STATIC_REGISTERED):
                await hass.http.async_register_static_paths(
                    [StaticPathConfig(FRONTEND_URL_BASE, str(FRONTEND_PATH), cache_headers=False)]
                )
                hass.data[_STATIC_REGISTERED] = True

            urls: dict[str, str] = {}
            digest, existing_files = await hass.async_add_executor_job(_frontend_assets_info, FRONTEND_PATH, CARD_FILES)
            for filename in existing_files:
                url = f"{FRONTEND_URL_BASE}/{filename}"
                urls[url] = f"{url}?v={integration.version}-{digest}"

            await _async_register_resources(hass, urls)
        except (HomeAssistantError, OSError):
            _LOGGER.exception("Unable to register disaster dashboard card frontend")
        else:
            hass.data[_REGISTERED] = True


async def _async_register_resources(hass: HomeAssistant, urls: dict[str, str]) -> None:
    """Reconcile the storage collection, or fall back to extra JS URLs in YAML mode."""
    lovelace = hass.data.get(LOVELACE_DATA)
    resources = lovelace.resources if lovelace is not None else None

    if not isinstance(resources, ResourceStorageCollection):
        added = hass.data.setdefault(_EXTRA_JS_URLS, [])
        for url in urls.values():
            add_extra_js_url(hass, url)
            added.append(url)
        return

    await resources.async_get_info()
    by_base_url: dict[str, list[dict]] = {}
    for item in resources.async_items():
        by_base_url.setdefault(_base_url(item["url"]), []).append(item)

    for legacy_url in LEGACY_CARD_URLS:
        for item in by_base_url.get(legacy_url, []):
            await resources.async_delete_item(item["id"])
            _LOGGER.info("Removed legacy dashboard resource %s", item["url"])

    for base_url, versioned_url in urls.items():
        existing = by_base_url.get(base_url, [])
        if not existing:
            await resources.async_create_item({"url": versioned_url, "res_type": "module"})
            continue
        first, *duplicates = existing
        if first.get("url") != versioned_url or (first.get("res_type") or first.get("type")) != "module":
            await resources.async_update_item(first["id"], {"url": versioned_url, "res_type": "module"})
        for item in duplicates:
            await resources.async_delete_item(item["id"])
            _LOGGER.info("Removed duplicate dashboard resource %s", item["url"])


async def async_unregister_frontend(hass: HomeAssistant) -> None:
    """Remove the integration's Lovelace resources (called when the last entry is removed)."""
    async with _lock(hass):
        lovelace = hass.data.get(LOVELACE_DATA)
        resources = lovelace.resources if lovelace is not None else None
        owned = {*CARD_URLS, *LEGACY_CARD_URLS}
        try:
            if isinstance(resources, ResourceStorageCollection):
                await resources.async_get_info()
                for item in list(resources.async_items()):
                    if _base_url(item["url"]) in owned:
                        await resources.async_delete_item(item["id"])
                        _LOGGER.info("Removed dashboard resource %s", item["url"])
            for url in hass.data.pop(_EXTRA_JS_URLS, []):
                remove_extra_js_url(hass, url)
        except HomeAssistantError:
            _LOGGER.exception("Unable to remove disaster dashboard card resources")
        # The static path cannot be unregistered, so _STATIC_REGISTERED stays set.
        hass.data.pop(_REGISTERED, None)
