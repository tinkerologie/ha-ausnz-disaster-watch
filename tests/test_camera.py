"""Unit tests for Australian Disaster Watch camera platform."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.ausnz_disaster_watch.camera import AustralianDisasterWatchCamera, async_setup_entry
from custom_components.ausnz_disaster_watch.const import DOMAIN
from custom_components.ausnz_disaster_watch.coordinator import AustralianDisasterWatchCoordinator
from custom_components.ausnz_disaster_watch.models import DisasterCameraItem, DisasterCoordinatorData
from homeassistant.core import HomeAssistant


def _camera(camera_id: str, name: str = "Camera", **extra: object) -> DisasterCameraItem:
    return DisasterCameraItem(id=camera_id, name=name, image_url=f"https://example.com/{camera_id}.jpg", **extra)


async def test_camera_entities_follow_coordinator_data(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Cameras that appear are added and cameras that disappear are removed (#19)."""
    mock_config_entry.add_to_hass(hass)
    coordinator = AustralianDisasterWatchCoordinator(hass, mock_config_entry)
    coordinator.data = DisasterCoordinatorData(cameras=[])
    mock_config_entry.runtime_data = coordinator

    async_add_entities = MagicMock()
    await async_setup_entry(hass, mock_config_entry, async_add_entities)
    assert not async_add_entities.called

    # A camera appears after setup
    coordinator.async_set_updated_data(DisasterCoordinatorData(cameras=[_camera("a", "Beachmere")]))
    (first,) = async_add_entities.call_args[0][0]
    assert isinstance(first, AustralianDisasterWatchCamera)
    assert first.name == "Beachmere"

    # A second camera appears; the first one is not added again
    async_add_entities.reset_mock()
    coordinator.async_set_updated_data(DisasterCoordinatorData(cameras=[_camera("a"), _camera("b")]))
    (second,) = async_add_entities.call_args[0][0]
    assert second.camera_id == "b"

    # The first camera disappears: its entity is removed
    first.hass = hass
    first.async_remove = AsyncMock()  # type: ignore[method-assign]
    second.async_remove = AsyncMock()  # type: ignore[method-assign]
    async_add_entities.reset_mock()
    coordinator.async_set_updated_data(DisasterCoordinatorData(cameras=[_camera("b")]))
    await hass.async_block_till_done()
    first.async_remove.assert_awaited_once()
    assert not async_add_entities.called

    # A removed entity that never got hass is just forgotten
    coordinator.async_set_updated_data(DisasterCoordinatorData(cameras=[]))
    await hass.async_block_till_done()
    second.async_remove.assert_not_awaited()


async def test_camera_attributes_and_snapshots(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Attributes and snapshots come from the camera's current data."""
    mock_config_entry.add_to_hass(hass)
    coordinator = AustralianDisasterWatchCoordinator(hass, mock_config_entry)
    coordinator.data = DisasterCoordinatorData(
        cameras=[
            _camera("goodna", "Goodna Flood Camera", suburb="Goodna", latitude=-27.6083, longitude=152.8942),
            _camera("minimal", "Minimal Cam"),
        ]
    )

    camera = AustralianDisasterWatchCamera(coordinator, "goodna")
    camera.hass = hass

    assert camera.name == "Goodna Flood Camera"
    assert camera.icon == "mdi:cctv"
    assert camera.unique_id == f"{mock_config_entry.entry_id}_camera_goodna"
    assert camera.available is True

    attrs = camera.extra_state_attributes
    assert attrs["image_url"] == "https://example.com/goodna.jpg"
    assert attrs["suburb"] == "Goodna"
    assert attrs["latitude"] == -27.6083
    assert attrs["longitude"] == 152.8942

    minimal = AustralianDisasterWatchCamera(coordinator, "minimal")
    assert minimal.extra_state_attributes == {"image_url": "https://example.com/minimal.jpg", "integration": DOMAIN}

    mock_resp_200 = AsyncMock()
    mock_resp_200.status = 200
    mock_resp_200.read = AsyncMock(return_value=b"\xff\xd8\xff\xe0mock_image_bytes")
    mock_session = MagicMock()
    mock_session.get.return_value.__aenter__.return_value = mock_resp_200

    assert camera.entity_picture is None
    with patch("custom_components.ausnz_disaster_watch.camera.async_get_clientsession", return_value=mock_session):
        assert await camera.async_camera_image() == b"\xff\xd8\xff\xe0mock_image_bytes"
        assert camera.entity_picture is not None

    mock_resp_404 = AsyncMock()
    mock_resp_404.status = 404
    mock_session.get.return_value.__aenter__.return_value = mock_resp_404
    with patch("custom_components.ausnz_disaster_watch.camera.async_get_clientsession", return_value=mock_session):
        assert await camera.async_camera_image() is None

    mock_session.get.side_effect = RuntimeError("Connection timeout")
    with patch("custom_components.ausnz_disaster_watch.camera.async_get_clientsession", return_value=mock_session):
        assert await camera.async_camera_image() is None

    # The camera is no longer listed: unavailable, no snapshot request, no attributes
    coordinator.data = DisasterCoordinatorData(cameras=[])
    assert camera.available is False
    assert camera.extra_state_attributes == {"integration": DOMAIN}
    mock_session.get.reset_mock()
    with patch("custom_components.ausnz_disaster_watch.camera.async_get_clientsession", return_value=mock_session):
        assert await camera.async_camera_image() is None
    mock_session.get.assert_not_called()

    # An entity created for an unknown ID falls back to the ID as its name
    assert AustralianDisasterWatchCamera(coordinator, "gone").name == "gone"
