"""Unit tests for Australian Disaster Watch camera platform."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.ausnz_disaster_watch.camera import AustralianDisasterWatchCamera, async_setup_entry
from custom_components.ausnz_disaster_watch.const import DOMAIN
from custom_components.ausnz_disaster_watch.coordinator import AustralianDisasterWatchCoordinator
from custom_components.ausnz_disaster_watch.models import DisasterCameraItem, DisasterCoordinatorData
from homeassistant.core import HomeAssistant


async def test_camera_setup_entry_with_cameras(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test camera platform setup when cameras are present."""
    mock_config_entry.add_to_hass(hass)
    coordinator = AustralianDisasterWatchCoordinator(hass, mock_config_entry)

    cam1 = DisasterCameraItem(
        id="cam_1",
        name="Test Camera 1",
        image_url="https://example.com/cam1.jpg",
        suburb="Caboolture",
        latitude=-27.08,
        longitude=152.95,
    )
    coordinator.data = DisasterCoordinatorData(cameras=[cam1])
    hass.data.setdefault(DOMAIN, {})[mock_config_entry.entry_id] = coordinator

    async_add_entities = MagicMock()
    await async_setup_entry(hass, mock_config_entry, async_add_entities)

    assert async_add_entities.called
    added = async_add_entities.call_args[0][0]
    assert len(added) == 1
    assert isinstance(added[0], AustralianDisasterWatchCamera)
    assert added[0].name == "Test Camera 1"


async def test_camera_setup_entry_without_cameras(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test camera platform setup when coordinator has no cameras."""
    mock_config_entry.add_to_hass(hass)
    coordinator = AustralianDisasterWatchCoordinator(hass, mock_config_entry)
    coordinator.data = DisasterCoordinatorData(cameras=[])
    hass.data.setdefault(DOMAIN, {})[mock_config_entry.entry_id] = coordinator

    async_add_entities = MagicMock()
    await async_setup_entry(hass, mock_config_entry, async_add_entities)

    assert not async_add_entities.called


async def test_camera_attributes_and_snapshots(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test camera entity attributes and snapshot fetching."""
    mock_config_entry.add_to_hass(hass)
    coordinator = AustralianDisasterWatchCoordinator(hass, mock_config_entry)

    cam_item = DisasterCameraItem(
        id="qld_goodna",
        name="Goodna Flood Camera",
        image_url="https://example.com/goodna.jpg",
        suburb="Goodna",
        latitude=-27.6083,
        longitude=152.8942,
    )

    camera = AustralianDisasterWatchCamera(coordinator, cam_item)
    camera.hass = hass

    assert camera.name == "Goodna Flood Camera"
    assert camera.icon == "mdi:cctv"
    assert camera.unique_id == f"{mock_config_entry.entry_id}_camera_qld_goodna"

    attrs = camera.extra_state_attributes
    assert attrs["image_url"] == "https://example.com/goodna.jpg"
    assert attrs["suburb"] == "Goodna"
    assert attrs["latitude"] == -27.6083
    assert attrs["longitude"] == 152.8942

    # Camera with no suburb and no coordinates
    cam_minimal = DisasterCameraItem(
        id="minimal",
        name="Minimal Cam",
        image_url="https://example.com/min.jpg",
    )
    cam_min_entity = AustralianDisasterWatchCamera(coordinator, cam_minimal)
    min_attrs = cam_min_entity.extra_state_attributes
    assert min_attrs == {"image_url": "https://example.com/min.jpg"}

    # Test snapshot fetch: HTTP 200
    mock_resp_200 = AsyncMock()
    mock_resp_200.status = 200
    mock_resp_200.read = AsyncMock(return_value=b"\xff\xd8\xff\xe0mock_image_bytes")

    mock_session = MagicMock()
    mock_session.get.return_value.__aenter__.return_value = mock_resp_200

    with patch("custom_components.ausnz_disaster_watch.camera.async_get_clientsession", return_value=mock_session):
        image_bytes = await camera.async_camera_image()
        assert image_bytes == b"\xff\xd8\xff\xe0mock_image_bytes"

    # Test snapshot fetch: HTTP 404
    mock_resp_404 = AsyncMock()
    mock_resp_404.status = 404
    mock_session.get.return_value.__aenter__.return_value = mock_resp_404

    with patch("custom_components.ausnz_disaster_watch.camera.async_get_clientsession", return_value=mock_session):
        assert await camera.async_camera_image() is None

    # Test snapshot fetch: Network error
    mock_session.get.side_effect = RuntimeError("Connection timeout")

    with patch("custom_components.ausnz_disaster_watch.camera.async_get_clientsession", return_value=mock_session):
        assert await camera.async_camera_image() is None
