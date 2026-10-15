"""Unit tests for frontend card registration and resource cleanup (#22, #43)."""

from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.ausnz_disaster_watch.const import DOMAIN
from custom_components.ausnz_disaster_watch.frontend import (
    _EXTRA_JS_URLS,
    _REGISTERED,
    _STATIC_REGISTERED,
    CARD_FILES,
    FRONTEND_PATH,
    _async_register_resources,
    _frontend_assets_info,
    _frontend_digest,
    async_register_frontend,
    async_unregister_frontend,
)
from homeassistant.components.lovelace.const import LOVELACE_DATA
from homeassistant.components.lovelace.resources import ResourceStorageCollection
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

CARD = "/ausnz_disaster_watch/ausnz-disaster-card.js"
LEGACY = "/ausnz_disaster_watch/aus-disaster-card.js"


def _storage(hass: HomeAssistant, items: list[dict[str, Any]]) -> MagicMock:
    """Install a mock Lovelace storage collection holding ``items``."""
    resources = MagicMock(spec=ResourceStorageCollection)
    resources.async_get_info = AsyncMock()
    resources.async_items = MagicMock(return_value=items)
    resources.async_create_item = AsyncMock()
    resources.async_update_item = AsyncMock()
    resources.async_delete_item = AsyncMock()
    lovelace = MagicMock()
    lovelace.resources = resources
    hass.data[LOVELACE_DATA] = lovelace
    return resources


def test_frontend_digest_and_assets() -> None:
    """The committed bundle exists and only the card suite bundle is shipped."""
    digest = _frontend_digest(FRONTEND_PATH)
    assert isinstance(digest, str)
    assert len(digest) == 8

    digest2, files = _frontend_assets_info(FRONTEND_PATH, CARD_FILES)
    assert digest2 == digest
    assert files == ["ausnz-disaster-card.js"]
    # The legacy stub is gone (#22); the map is a lazily loaded chunk (#41).
    assert not (FRONTEND_PATH / "aus-disaster-card.js").exists()
    assert sorted(p.name for p in FRONTEND_PATH.glob("*.js") if p.name != "ausnz-disaster-card.js")


def test_frontend_digest_edge_cases(tmp_path: Path) -> None:
    """Test frontend digest with non-directory and empty directory."""
    assert _frontend_digest(tmp_path / "does_not_exist") == "none"

    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()
    assert _frontend_digest(empty_dir) == "none"


async def test_frontend_registration(hass: HomeAssistant) -> None:
    """Registration serves the static path once and is idempotent."""
    hass.config.components.add("http")
    hass.config.components.add("frontend")

    mock_http = MagicMock()
    mock_http.async_register_static_paths = AsyncMock()
    hass.http = mock_http

    with patch(
        "custom_components.ausnz_disaster_watch.frontend._async_register_resources",
        new_callable=AsyncMock,
    ) as mock_res:
        await async_register_frontend(hass)
        await async_register_frontend(hass)
        mock_http.async_register_static_paths.assert_called_once()
        mock_res.assert_called_once()
        urls = mock_res.call_args[0][1]
        assert list(urls) == [CARD]
        assert urls[CARD].startswith(f"{CARD}?v=")
    assert hass.data[_REGISTERED] is True

    # After cleanup the resource is registered again, but the static path is not.
    hass.data.pop(_REGISTERED)
    with patch(
        "custom_components.ausnz_disaster_watch.frontend._async_register_resources",
        new_callable=AsyncMock,
    ) as mock_res:
        await async_register_frontend(hass)
        mock_res.assert_called_once()
    mock_http.async_register_static_paths.assert_called_once()
    assert hass.data[_STATIC_REGISTERED] is True


async def test_frontend_skipped_when_running_without_http(hass: HomeAssistant) -> None:
    """Test registration skipped when running without http/frontend."""
    hass.config.components = set()
    await async_register_frontend(hass)
    assert _REGISTERED not in hass.data


@pytest.mark.parametrize("has_entry", [True, False])
async def test_frontend_deferred_on_start(hass: HomeAssistant, has_entry: bool) -> None:
    """Deferred registration runs at start only while an entry still exists."""
    hass.config.components = set()
    if has_entry:
        MockConfigEntry(domain=DOMAIN, data={}).add_to_hass(hass)
    with (
        patch.object(hass, "is_running", False),
        patch("custom_components.ausnz_disaster_watch.frontend.async_at_started") as mock_at_started,
    ):
        await async_register_frontend(hass)
        mock_at_started.assert_called_once()
        callback = mock_at_started.call_args[0][1]
        with patch("custom_components.ausnz_disaster_watch.frontend.async_register_frontend") as mock_reg:
            await callback(hass)
            assert mock_reg.called is has_entry


async def test_frontend_registration_error_handled(hass: HomeAssistant) -> None:
    """A failing registration is logged and retried on the next call."""
    hass.config.components.add("http")
    hass.config.components.add("frontend")
    mock_http = MagicMock()
    mock_http.async_register_static_paths = AsyncMock(side_effect=OSError("Disk failure"))
    hass.http = mock_http

    await async_register_frontend(hass)
    assert _REGISTERED not in hass.data


async def test_async_register_resources_fallback(hass: HomeAssistant) -> None:
    """YAML mode falls back to extra JS URLs and records them for cleanup."""
    with patch("custom_components.ausnz_disaster_watch.frontend.add_extra_js_url") as mock_add_extra:
        await _async_register_resources(hass, {CARD: f"{CARD}?v=1"})
        mock_add_extra.assert_called_once_with(hass, f"{CARD}?v=1")
    assert hass.data[_EXTRA_JS_URLS] == [f"{CARD}?v=1"]


async def test_async_register_resources_creates(hass: HomeAssistant) -> None:
    """A missing resource is created as a module."""
    resources = _storage(hass, [{"id": "x", "url": "/other/card.js", "res_type": "module"}])
    await _async_register_resources(hass, {CARD: f"{CARD}?v=2"})
    resources.async_create_item.assert_awaited_once_with({"url": f"{CARD}?v=2", "res_type": "module"})
    resources.async_update_item.assert_not_called()
    resources.async_delete_item.assert_not_called()


async def test_async_register_resources_reconciles(hass: HomeAssistant) -> None:
    """Legacy and duplicate resources are deleted; the first canonical item is updated; others stay."""
    resources = _storage(
        hass,
        [
            {"id": "legacy-q", "url": f"{LEGACY}?v=1.0.0-fe92c260", "res_type": "module"},
            {"id": "legacy", "url": LEGACY, "res_type": "module"},
            {"id": "card", "url": f"{CARD}?v=old", "type": "js"},
            {"id": "dupe", "url": f"{CARD}?v=older", "res_type": "module"},
            {"id": "other", "url": "/hacsfiles/other-card.js", "res_type": "module"},
            {"id": "lookalike", "url": "/elsewhere/aus-disaster-card.js", "res_type": "module"},
        ],
    )
    await _async_register_resources(hass, {CARD: f"{CARD}?v=2"})
    resources.async_create_item.assert_not_called()
    resources.async_update_item.assert_awaited_once_with("card", {"url": f"{CARD}?v=2", "res_type": "module"})
    deleted = [call.args[0] for call in resources.async_delete_item.await_args_list]
    assert deleted == ["legacy-q", "legacy", "dupe"]


async def test_async_register_resources_up_to_date(hass: HomeAssistant) -> None:
    """An up-to-date resource is left alone."""
    resources = _storage(hass, [{"id": "card", "url": f"{CARD}?v=2", "res_type": "module"}])
    await _async_register_resources(hass, {CARD: f"{CARD}?v=2"})
    resources.async_update_item.assert_not_called()
    resources.async_create_item.assert_not_called()
    resources.async_delete_item.assert_not_called()


async def test_unregister_storage(hass: HomeAssistant) -> None:
    """Cleanup deletes only the integration's resources and resets the registration flag."""
    resources = _storage(
        hass,
        [
            {"id": "card", "url": f"{CARD}?v=2", "res_type": "module"},
            {"id": "legacy", "url": LEGACY, "res_type": "module"},
            {"id": "other", "url": "/hacsfiles/other-card.js", "res_type": "module"},
        ],
    )
    hass.data[_REGISTERED] = True
    hass.data[_STATIC_REGISTERED] = True
    await async_unregister_frontend(hass)
    deleted = [call.args[0] for call in resources.async_delete_item.await_args_list]
    assert deleted == ["card", "legacy"]
    assert _REGISTERED not in hass.data
    assert hass.data[_STATIC_REGISTERED] is True


async def test_unregister_yaml_mode(hass: HomeAssistant) -> None:
    """Cleanup removes extra JS URLs added in YAML mode."""
    hass.data[_EXTRA_JS_URLS] = [f"{CARD}?v=1"]
    with patch("custom_components.ausnz_disaster_watch.frontend.remove_extra_js_url") as mock_remove:
        await async_unregister_frontend(hass)
        mock_remove.assert_called_once_with(hass, f"{CARD}?v=1")
    assert _EXTRA_JS_URLS not in hass.data


async def test_unregister_error_logged(hass: HomeAssistant, caplog: pytest.LogCaptureFixture) -> None:
    """A storage failure during cleanup is logged and does not raise."""
    resources = _storage(hass, [{"id": "card", "url": CARD, "res_type": "module"}])
    resources.async_delete_item.side_effect = HomeAssistantError("boom")
    hass.data[_REGISTERED] = True
    await async_unregister_frontend(hass)
    assert "Unable to remove disaster dashboard card resources" in caplog.text
    assert _REGISTERED not in hass.data
