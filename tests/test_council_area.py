"""Tests for the council area lookup and the in_council_area tags (#94)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.ausnz_disaster_watch.coordinator import (
    AustralianDisasterWatchCoordinator,
    OptionalFeedTimeoutError,
    tag_council_area,
)
from custom_components.ausnz_disaster_watch.models import (
    CanonicalHazard,
    DisasterCameraItem,
    DisasterCoordinatorData,
    HazardType,
    PowerOutageItem,
    ReliefFacilityItem,
    RoadClosureItem,
    WarningLevel,
)
from custom_components.ausnz_disaster_watch.providers.base import ProviderUnavailableError
from custom_components.ausnz_disaster_watch.providers.council_area import (
    ABS_LGA_AREA_URL,
    COUNCIL_AREA_RETRY,
    COUNCIL_AREA_STORAGE_KEY,
    STATS_NZ_TA_AREA_URL,
    CouncilArea,
    CouncilAreaService,
    async_remove_stored_council_area,
    parse_council_area,
)
from custom_components.ausnz_disaster_watch.sensor import (
    HighestWarningLevelSensor,
    PowerOutagesCountSensor,
    ReliefFacilitiesCountSensor,
    RoadClosuresCountSensor,
)
from homeassistant.core import HomeAssistant

# A 1 x 1 degree square council with a 0.2 degree hole in the middle (lon, lat as ArcGIS gives them)
OUTER = [[152.0, -28.0], [153.0, -28.0], [153.0, -27.0], [152.0, -27.0], [152.0, -28.0]]
HOLE = [[152.4, -27.6], [152.4, -27.4], [152.6, -27.4], [152.6, -27.6], [152.4, -27.6]]
HOME = (-27.2, 152.2)


def _payload(code: str = "35010", name: str = "Moreton Bay", nz: bool = False) -> dict[str, Any]:
    fields = ("TA2026_V1_00", "TA2026_V1_00_NAME") if nz else ("lga_code_2021", "lga_name_2021")
    return {
        "features": [
            {"attributes": {fields[0]: None, fields[1]: None}, "geometry": {"rings": [OUTER]}},  # no code: skipped
            {"attributes": {fields[0]: code, fields[1]: name}, "geometry": {"rings": [OUTER, HOLE, [[1, 2]]]}},
        ]
    }


def _area() -> CouncilArea:
    area = parse_council_area(_payload(), nz=False)
    assert area is not None
    return area


def _hazard(lat: float, lon: float, area: Any = None) -> CanonicalHazard:
    return CanonicalHazard(
        id=f"h{lat}{lon}",
        source="s",
        title="t",
        hazard_type=HazardType.BUSHFIRE,
        warning_level=WarningLevel.ADVICE,
        latitude=lat,
        longitude=lon,
        updated_at=datetime(2026, 10, 16, tzinfo=UTC),
        area=area,
    )


def test_parse_council_area() -> None:
    """The registry names a council it lists; the boundary keeps its hole; short rings are dropped."""
    area = _area()
    assert (area.code, area.name) == ("35010", "City of Moreton Bay")
    assert len(area.rings) == 2
    assert area.rings[0][0] == (-28.0, 152.0)
    assert area.bbox == (-28.0, 152.0, -27.0, 153.0)

    unlisted = parse_council_area(_payload("99999", "Nowhere"), nz=False)
    assert unlisted is not None
    assert unlisted.name == "Nowhere"
    wellington = parse_council_area(_payload("047", "Wellington City", nz=True), nz=True)
    assert wellington is not None
    assert (wellington.code, wellington.name) == ("047", "Wellington City")

    assert parse_council_area({"features": []}, nz=False) is None
    assert parse_council_area({"features": [{"attributes": {}, "geometry": None}]}, nz=False) is None
    for bad in ({"error": {"code": 400}}, [], None):
        with pytest.raises(ProviderUnavailableError):
            parse_council_area(bad, nz=False)


def test_contains() -> None:
    """Even-odd rule: inside the outer ring and outside the hole; the bounding box is checked first."""
    area = _area()
    assert area.contains(*HOME) is True
    assert area.contains(-27.5, 152.5) is False  # in the hole
    assert area.contains(-26.0, 152.5) is False  # outside the box
    assert area.contains(None, 152.5) is None
    assert area.contains(-27.5, None) is None


def test_tag_hazard() -> None:
    """A hazard is in the council when its point is, or when its area overlaps the council."""
    area = _area()
    assert area.tag_hazard(_hazard(*HOME)) is True
    outside = (-26.5, 152.5)
    assert area.tag_hazard(_hazard(*outside)) is False
    # Area reaching into the council (a vertex inside), point outside
    reaching = (((-26.5, 152.5), (-26.5, 152.6), (-27.1, 152.6), (-27.1, 152.5)),)
    assert area.tag_hazard(_hazard(*outside, area=reaching)) is True
    # Area covering the whole council (council vertices inside the area)
    covering = (((-29.0, 151.0), (-29.0, 154.0), (-26.0, 154.0), (-26.0, 151.0)),)
    assert area.tag_hazard(_hazard(-26.2, 151.2, area=covering)) is True
    # Box overlaps, shapes do not (the area sits in the hole); far away; empty ring
    in_hole = (((-27.55, 152.45), (-27.55, 152.55), (-27.45, 152.55), (-27.45, 152.45)),)
    assert area.tag_hazard(_hazard(-27.5, 152.5, area=in_hole)) is False
    far = (((-20.0, 140.0), (-20.0, 141.0), (-19.0, 141.0)),)
    assert area.tag_hazard(_hazard(-19.5, 140.5, area=far)) is False
    assert area.overlaps(((),)) is False


def test_round_trip() -> None:
    """The stored boundary survives the Store's JSON; anything else is ignored."""
    area = _area()
    restored = CouncilArea.from_dict(area.to_dict())
    assert restored == area
    assert restored is not None
    assert restored.bbox == area.bbox
    for bad in (None, {}, {"code": "1", "name": "x", "rings": []}, {"code": "1", "name": "x", "rings": [[[1, 2]]]}):
        assert CouncilArea.from_dict(bad) is None
    assert CouncilArea.from_dict({"code": "1", "name": "x", "rings": [["ab"]]}) is None


def _service(hass: HomeAssistant, payload: Any, state: str = "QLD", entry_id: str | None = "entry1") -> Any:
    service = CouncilAreaService(
        hass, AsyncMock(), {"state": state, "latitude": HOME[0], "longitude": HOME[1]}, entry_id=entry_id
    )
    fetch = AsyncMock(side_effect=payload) if isinstance(payload, BaseException) else AsyncMock(return_value=payload)
    service.async_fetch_feed_json = fetch
    return service


async def test_service_looks_up_once_per_location(hass: HomeAssistant, hass_storage: dict[str, Any]) -> None:
    """The boundary is fetched once, stored, and restored after a restart without a request."""
    key = COUNCIL_AREA_STORAGE_KEY.format(entry_id="entry1")
    service = _service(hass, _payload())
    assert await service.async_fetch_hazards() == []
    assert [source.key for source in service.data_sources] == ["abs_lga"]
    await service.async_update()
    await service.async_update()
    service.async_fetch_feed_json.assert_awaited_once()
    assert service.async_fetch_feed_json.await_args.args[0] == ABS_LGA_AREA_URL.format(lat=HOME[0], lon=HOME[1])
    assert service.area is not None
    assert service.area.name == "City of Moreton Bay"
    assert hass_storage[key]["data"]["location"] == list(HOME)

    restarted = _service(hass, _payload())
    await restarted.async_update()
    restarted.async_fetch_feed_json.assert_not_awaited()
    assert restarted.area == service.area

    # A move looks the new point up (here: in no council, which is stored too)
    restarted.set_location(-10.0, 120.0)
    restarted.async_fetch_feed_json.return_value = {"features": []}
    await restarted.async_update()
    assert restarted.area is None
    assert hass_storage[key]["data"] == {"location": [-10.0, 120.0], "area": None}
    again = _service(hass, _payload())
    again.set_location(-10.0, 120.0)
    await again.async_update()
    again.async_fetch_feed_json.assert_not_awaited()
    assert again.area is None

    # A stored boundary for another point is not used
    elsewhere = _service(hass, _payload())
    await elsewhere.async_update()
    elsewhere.async_fetch_feed_json.assert_awaited_once()

    await async_remove_stored_council_area(hass, "entry1")
    assert key not in hass_storage


async def test_service_nz_and_no_location(hass: HomeAssistant) -> None:
    """NZ entries use the Stats NZ territorial authorities; an entry without a point has no area."""
    service = _service(hass, _payload("047", "Wellington City", nz=True), state="NZ", entry_id=None)
    assert [source.key for source in service.data_sources] == ["stats_nz_ta"]
    await service.async_update()
    assert service.async_fetch_feed_json.await_args.args[0] == STATS_NZ_TA_AREA_URL.format(lat=HOME[0], lon=HOME[1])
    assert service.area is not None
    assert service.area.name == "Wellington City"

    service.config = {"state": "NZ"}
    await service.async_update()
    assert service.area is None


async def test_service_failure_retries_later(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    """A failed lookup leaves no area and is retried after the retry interval, not every refresh."""
    freezer.move_to("2026-10-16T00:00:00+00:00")
    service = _service(hass, ProviderUnavailableError("down"), entry_id=None)
    await service.async_update()
    assert service.area is None
    await service.async_update()
    service.async_fetch_feed_json.assert_awaited_once()

    freezer.tick(COUNCIL_AREA_RETRY + timedelta(seconds=1))
    service.async_fetch_feed_json.side_effect = None
    service.async_fetch_feed_json.return_value = _payload()
    await service.async_update()
    assert service.area is not None

    # After a move, a failed lookup drops the old point's area instead of tagging with it
    service.set_location(-10.0, 120.0)
    service.async_fetch_feed_json.return_value = {"error": {"code": 500}}
    await service.async_update()
    assert service.area is None

    # A failure at one point does not hold up the lookup of another
    service.set_location(*HOME)
    service.async_fetch_feed_json.return_value = _payload()
    await service.async_update()
    assert service.area is not None


async def test_service_ignores_unreadable_store(hass: HomeAssistant, hass_storage: dict[str, Any]) -> None:
    """A damaged or foreign Store only means one more lookup."""
    key = COUNCIL_AREA_STORAGE_KEY.format(entry_id="entry1")
    hass_storage[key] = {"version": 1, "minor_version": 1, "key": key, "data": ["not", "a", "dict"]}
    service = _service(hass, _payload())
    await service.async_update()
    service.async_fetch_feed_json.assert_awaited_once()

    with patch("homeassistant.helpers.storage.Store.async_load", AsyncMock(side_effect=OSError("disk"))):
        broken = _service(hass, _payload())
        await broken.async_update()
    broken.async_fetch_feed_json.assert_awaited_once()

    # A stored boundary that cannot be read is looked up again
    hass_storage[key] = {
        "version": 1,
        "minor_version": 1,
        "key": key,
        "data": {"location": list(HOME), "area": {"x": 1}},
    }
    damaged = _service(hass, _payload())
    await damaged.async_update()
    damaged.async_fetch_feed_json.assert_awaited_once()
    assert damaged.area is not None


def _aux() -> dict[str, Any]:
    return {
        "road_closures": [
            RoadClosureItem(id="r1", latitude=HOME[0], longitude=HOME[1]),
            RoadClosureItem(id="r2", latitude=-26.0, longitude=152.5),
            RoadClosureItem(id="r3"),
        ],
        "relief_facilities": [
            ReliefFacilityItem(id="f1", facility_type="sandbag_station", name="S", latitude=-27.5, longitude=152.5)
        ],
        "power_outages": [PowerOutageItem(suburb="A", latitude=HOME[0], longitude=HOME[1])],
        "cameras": [
            DisasterCameraItem(id="c1", name="C", image_url="https://x/c.jpg", latitude=-26.0, longitude=152.5)
        ],
    }


def test_tag_council_area() -> None:
    """Every listed item and hazard is tagged; unlocated items and an unknown council give None."""
    aux = _aux()
    hazards = [_hazard(*HOME), _hazard(-26.0, 152.5)]
    tag_council_area(_area(), hazards, aux)
    assert [h.in_council_area for h in hazards] == [True, False]
    assert [r.in_council_area for r in aux["road_closures"]] == [True, False, None]
    assert aux["relief_facilities"][0].in_council_area is False  # in the hole
    assert aux["power_outages"][0].in_council_area is True
    assert aux["cameras"][0].in_council_area is False
    assert hazards[0].to_safe_attributes()["in_council_area"] is True

    tag_council_area(None, hazards, aux)
    assert [h.in_council_area for h in hazards] == [None, None]
    assert aux["power_outages"][0].in_council_area is None
    assert "in_council_area" not in hazards[0].to_safe_attributes()


async def test_coordinator_council_area(hass: HomeAssistant, mock_config_entry: MockConfigEntry) -> None:
    """The coordinator publishes the council's name and code, and credits the boundary source once in use."""
    coordinator = AustralianDisasterWatchCoordinator(hass, mock_config_entry)
    assert coordinator.council_area is None
    assert coordinator.council_area_summary is None
    assert "abs_lga" not in [source.key for source in coordinator.data_sources]

    coordinator.council_area_service.area = _area()
    assert coordinator.council_area_summary == {"name": "City of Moreton Bay", "code": "35010"}
    assert [source.key for source in coordinator.data_sources].count("abs_lga") == 1

    # The count sensors keep their radius states and add the council totals for the cards
    aux = _aux()
    tag_council_area(coordinator.council_area, [], aux)
    coordinator.data = DisasterCoordinatorData(
        road_closures=aux["road_closures"],
        relief_facilities=aux["relief_facilities"],
        power_outages=[*aux["power_outages"], PowerOutageItem(suburb="B", customers_affected=7)],
    )
    roads = RoadClosuresCountSensor(coordinator)
    assert roads.native_value == 3
    assert roads.extra_state_attributes["council_area_count"] == 1
    assert ReliefFacilitiesCountSensor(coordinator).extra_state_attributes["council_area_count"] == 0
    outages = PowerOutagesCountSensor(coordinator)
    assert outages.native_value == 2
    assert outages.extra_state_attributes["council_area_count"] == 1
    assert outages.extra_state_attributes["council_area_customers_affected"] == 0
    level = HighestWarningLevelSensor(coordinator)
    assert level.extra_state_attributes["council_area"] == {"name": "City of Moreton Bay", "code": "35010"}

    coordinator.council_area_service.area = None
    assert roads.extra_state_attributes["council_area_count"] is None
    assert outages.extra_state_attributes["council_area_customers_affected"] is None
    assert level.extra_state_attributes["council_area"] is None

    # A lookup that outlives its timeout only skips the tags
    with patch.object(coordinator, "_async_optional", AsyncMock(side_effect=OptionalFeedTimeoutError("slow"))):
        await coordinator._async_update_council_area()
