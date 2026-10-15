"""Unit tests for frontend card registration."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from custom_components.ausnz_disaster_watch.frontend import (
    _REGISTERED,
    CARD_FILES,
    FRONTEND_PATH,
    _async_register_resources,
    _frontend_assets_info,
    _frontend_digest,
    async_register_frontend,
)
from homeassistant.components.lovelace.const import LOVELACE_DATA
from homeassistant.components.lovelace.resources import ResourceStorageCollection
from homeassistant.core import HomeAssistant


def test_frontend_digest_and_assets() -> None:
    """Test frontend digest generation and existing file discovery."""
    digest = _frontend_digest(FRONTEND_PATH)
    assert isinstance(digest, str)
    assert len(digest) == 8

    digest2, files = _frontend_assets_info(FRONTEND_PATH, CARD_FILES)
    assert digest2 == digest
    assert "aus-disaster-card.js" in files


def test_frontend_digest_edge_cases(tmp_path: Path) -> None:
    """Test frontend digest with non-directory and empty directory."""
    assert _frontend_digest(tmp_path / "does_not_exist") == "none"

    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()
    assert _frontend_digest(empty_dir) == "none"


async def test_frontend_registration(hass: HomeAssistant) -> None:
    """Test frontend registration registers static paths."""
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
        mock_http.async_register_static_paths.assert_called_once()
        mock_res.assert_called_once()


async def test_frontend_already_registered(hass: HomeAssistant) -> None:
    """Test calling registration when already registered does nothing."""
    hass.data[_REGISTERED] = True
    await async_register_frontend(hass)


async def test_frontend_skipped_when_running_without_http(hass: HomeAssistant) -> None:
    """Test registration skipped when running without http/frontend."""
    hass.config.components = set()
    await async_register_frontend(hass)


async def test_frontend_deferred_on_start(hass: HomeAssistant) -> None:
    """Test registration is deferred when hass is not yet running."""
    hass.config.components = set()
    with (
        patch.object(hass, "is_running", False),
        patch("custom_components.ausnz_disaster_watch.frontend.async_at_started") as mock_at_started,
    ):
        await async_register_frontend(hass)
        mock_at_started.assert_called_once()
        # Trigger the deferred callback
        callback = mock_at_started.call_args[0][1]
        with patch("custom_components.ausnz_disaster_watch.frontend.async_register_frontend") as mock_reg:
            await callback(hass)
            mock_reg.assert_called_once()


async def test_frontend_registration_error_handled(hass: HomeAssistant) -> None:
    """Test exception handling during frontend registration."""
    hass.config.components.add("http")
    hass.config.components.add("frontend")
    mock_http = MagicMock()
    mock_http.async_register_static_paths = AsyncMock(side_effect=OSError("Disk failure"))
    hass.http = mock_http

    await async_register_frontend(hass)


async def test_async_register_resources_fallback(hass: HomeAssistant) -> None:
    """Test fallback to add_extra_js_url when Lovelace collection is absent."""
    with patch("custom_components.ausnz_disaster_watch.frontend.add_extra_js_url") as mock_add_extra:
        await _async_register_resources(hass, {"/test/url": "/test/url?v=1"})
        mock_add_extra.assert_called_once()


async def test_async_register_resources_storage_collection(hass: HomeAssistant) -> None:
    """Test resource registration with ResourceStorageCollection."""
    mock_resources = MagicMock(spec=ResourceStorageCollection)
    mock_resources.async_get_info = AsyncMock()
    mock_resources.async_items = MagicMock(
        return_value=[
            {"id": "1", "url": "/existing/url?v=0", "res_type": "js"},  # Needs update
        ]
    )
    mock_resources.async_create_item = AsyncMock()
    mock_resources.async_update_item = AsyncMock()

    mock_lovelace = MagicMock()
    mock_lovelace.resources = mock_resources
    hass.data[LOVELACE_DATA] = mock_lovelace

    await _async_register_resources(
        hass,
        {
            "/new/url": "/new/url?v=1",
            "/existing/url": "/existing/url?v=2",
        },
    )
    mock_resources.async_create_item.assert_called_once()
    mock_resources.async_update_item.assert_called_once()
