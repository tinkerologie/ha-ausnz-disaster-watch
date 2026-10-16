"""Unit tests for Australian Disaster Watch camera platform."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.ausnz_disaster_watch.camera import (
    MAX_FRAME_BYTES,
    AustralianDisasterWatchCamera,
    async_setup_entry,
    image_content_type,
)
from custom_components.ausnz_disaster_watch.const import DOMAIN
from custom_components.ausnz_disaster_watch.coordinator import AustralianDisasterWatchCoordinator
from custom_components.ausnz_disaster_watch.models import DisasterCameraItem, DisasterCoordinatorData
from custom_components.ausnz_disaster_watch.providers.sources import DATA_SOURCES
from homeassistant.core import HomeAssistant

JPEG = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00mock_image_bytes"
PNG = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDRmock"
GIF = b"GIF89amock"
WEBP = b"RIFF\x10\x00\x00\x00WEBPVP8 mock"
# Live Traffic NSW answers a non-browser client with this page and HTTP 200 (#70)
HTML = (
    b"<html>\n    <head>\n    </head>\n    <h4>Page not found</h4>\n"
    b"    <p>The camera image you are looking for is temporarily unavailable.</p>\n</html>\n"
)


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

    # A camera that comes back while its old entity is still being removed is re-added
    # only after that removal finishes (otherwise HA rejects the duplicate unique ID)
    removal_done = asyncio.Event()

    async def slow_remove() -> None:
        await removal_done.wait()

    second.hass = hass
    second.async_remove = AsyncMock(side_effect=slow_remove)  # type: ignore[method-assign]
    async_add_entities.reset_mock()
    coordinator.async_set_updated_data(DisasterCoordinatorData(cameras=[]))
    await asyncio.sleep(0)
    coordinator.async_set_updated_data(DisasterCoordinatorData(cameras=[_camera("b")]))
    assert not async_add_entities.called
    removal_done.set()
    await hass.async_block_till_done()
    (returned,) = async_add_entities.call_args[0][0]
    assert returned.camera_id == "b"
    assert returned is not second
    second = returned
    second.async_remove = AsyncMock()  # type: ignore[method-assign]

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

    # Before any good frame, a failed fetch has nothing to show
    mock_session = MagicMock()
    mock_session.get.side_effect = RuntimeError("Connection timeout")
    assert camera.entity_picture is None
    with patch("custom_components.ausnz_disaster_watch.camera.async_get_clientsession", return_value=mock_session):
        assert await camera.async_camera_image() is None
    assert camera.entity_picture is None

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


@pytest.mark.parametrize(
    ("data", "expected"),
    [
        (JPEG, "image/jpeg"),
        (PNG, "image/png"),
        (GIF, "image/gif"),
        (WEBP, "image/webp"),
        (HTML, None),
        (b"", None),
        (b"RIFF\x10\x00\x00\x00WAVEfmt ", None),
        (b'{"error": "not found"}', None),
    ],
)
def test_image_content_type_from_magic_bytes(data: bytes, expected: str | None) -> None:
    """Only image magic bytes count, whatever the server says the body is (#70)."""
    assert image_content_type(data) == expected


async def test_snapshot_must_be_an_image(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, aioclient_mock: AiohttpClientMocker
) -> None:
    """HTML with HTTP 200 is never cached; a JPEG labelled octet-stream and a PNG are; failures keep the last frame (#70)."""
    mock_config_entry.add_to_hass(hass)
    coordinator = AustralianDisasterWatchCoordinator(hass, mock_config_entry)
    coordinator.data = DisasterCoordinatorData(cameras=[_camera("cam")])
    camera = AustralianDisasterWatchCamera(coordinator, "cam")
    camera.hass = hass
    url = "https://example.com/cam.jpg"

    def respond(**kwargs: object) -> None:
        aioclient_mock.clear_requests()
        aioclient_mock.get(url, **kwargs)  # type: ignore[arg-type]

    # An HTML placeholder with HTTP 200 and no earlier frame: nothing to show, nothing cached
    respond(text=HTML.decode(), headers={"Content-Type": "text/html"})
    assert await camera.async_camera_image() is None
    assert camera.entity_picture is None

    # QLDTraffic serves its "resized" JPEGs as binary/octet-stream
    respond(content=JPEG, headers={"Content-Type": "binary/octet-stream"})
    assert await camera.async_camera_image() == JPEG
    assert camera.content_type == "image/jpeg"
    assert camera.entity_picture is not None

    # The HTML placeholder later: the last good JPEG stays
    respond(text=HTML.decode(), headers={"Content-Type": "image/jpeg"})
    assert await camera.async_camera_image() == JPEG
    assert camera.content_type == "image/jpeg"

    respond(content=PNG, headers={"Content-Type": "image/png"})
    assert await camera.async_camera_image() == PNG
    assert camera.content_type == "image/png"

    # HTTP errors, network errors and oversized bodies keep the last good frame and its type
    respond(status=404)
    assert await camera.async_camera_image() == PNG
    respond(exc=TimeoutError())
    assert await camera.async_camera_image() == PNG
    respond(content=JPEG, headers={"Content-Length": str(MAX_FRAME_BYTES + 1)})
    assert await camera.async_camera_image() == PNG
    with patch("custom_components.ausnz_disaster_watch.camera.MAX_FRAME_BYTES", len(JPEG) - 1):
        respond(content=JPEG)
        assert await camera.async_camera_image() == PNG
    assert camera.content_type == "image/png"


def test_camera_credits_its_network_and_owner(hass: HomeAssistant, mock_config_entry: MockConfigEntry) -> None:
    """Road agency cameras credit their network and image owner; council cameras the entry (#70)."""
    coordinator = MagicMock()
    coordinator.attribution = "Entry credit"
    coordinator.entry.entry_id = "entry"
    coordinator.cameras = [
        _camera("qld", source_key="qldtraffic_cameras", owner="Douglas Shire Council", direction="North"),
        _camera("nz", source_key="nzta_cameras", description="Looking north", distance_km=1.2),
        _camera("council"),
        _camera("unknown", source_key="not_registered"),
    ]
    qld = AustralianDisasterWatchCamera(coordinator, "qld")
    assert qld.attribution == f"{DATA_SOURCES['qldtraffic_cameras'].attribution}. Image: Douglas Shire Council"
    assert qld.extra_state_attributes["owner"] == "Douglas Shire Council"
    assert qld.extra_state_attributes["direction"] == "North"
    assert qld.extra_state_attributes["network"] == "qldtraffic_cameras"
    nz = AustralianDisasterWatchCamera(coordinator, "nz")
    assert nz.attribution == DATA_SOURCES["nzta_cameras"].attribution
    assert nz.extra_state_attributes["description"] == "Looking north"
    assert nz.extra_state_attributes["distance_km"] == 1.2
    assert AustralianDisasterWatchCamera(coordinator, "council").attribution == "Entry credit"
    assert AustralianDisasterWatchCamera(coordinator, "unknown").attribution == "Entry credit"
    assert AustralianDisasterWatchCamera(coordinator, "gone").attribution == "Entry credit"
