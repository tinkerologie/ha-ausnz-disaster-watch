"""Unit tests for models, enums and CanonicalHazard."""

from collections.abc import Callable
from dataclasses import FrozenInstanceError, fields, replace
import datetime as dt
from datetime import UTC, date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

import pytest

from custom_components.ausnz_disaster_watch import models
from custom_components.ausnz_disaster_watch.models import (
    CanonicalHazard,
    DisasterCoordinatorData,
    DisasterWatchConfigModel,
    FireDangerDay,
    FireDangerOutlook,
    FireDangerRating,
    FireSeasonStatus,
    HazardType,
    HeatwaveArea,
    HeatwaveStatus,
    ModelValidationError,
    PowerOutageItem,
    TsunamiStatus,
    UVObservation,
    WarningLevel,
    to_dict,
    to_json_dict,
)


def test_warning_level_severity_ranks() -> None:
    """Test ordering of Australian Warning System severity ranks."""
    assert WarningLevel.EMERGENCY_WARNING.severity_rank == 4
    assert WarningLevel.WATCH_AND_ACT.severity_rank == 3
    assert WarningLevel.ADVICE.severity_rank == 2
    assert WarningLevel.INFORMATION.severity_rank == 1
    assert WarningLevel.UNKNOWN.severity_rank == 0

    assert WarningLevel.EMERGENCY_WARNING.severity_rank > WarningLevel.WATCH_AND_ACT.severity_rank
    assert WarningLevel.WATCH_AND_ACT.severity_rank > WarningLevel.ADVICE.severity_rank
    assert WarningLevel.ADVICE.severity_rank > WarningLevel.INFORMATION.severity_rank


def test_warning_level_parsing() -> None:
    """Test parsing string representations into WarningLevel."""
    assert WarningLevel.from_str("Emergency Warning - Evacuate") == WarningLevel.EMERGENCY_WARNING
    assert WarningLevel.from_str("Watch and Act") == WarningLevel.WATCH_AND_ACT
    assert WarningLevel.from_str("Watch & Act") == WarningLevel.WATCH_AND_ACT
    assert WarningLevel.from_str("Advice - Stay Informed") == WarningLevel.ADVICE
    assert WarningLevel.from_str("Information") == WarningLevel.INFORMATION
    assert WarningLevel.from_str("Routine") == WarningLevel.INFORMATION
    assert WarningLevel.from_str("Random Unknown") == WarningLevel.UNKNOWN
    assert WarningLevel.from_str(None) == WarningLevel.UNKNOWN


def test_hazard_type_parsing() -> None:
    """Test parsing hazard types from string."""
    assert HazardType.from_str("Bush Fire") == HazardType.BUSHFIRE
    assert HazardType.from_str("Grass fire") == HazardType.GRASS_FIRE
    assert HazardType.from_str("Structure Fire") == HazardType.METROPOLITAN_FIRE
    assert HazardType.from_str("River Flood Warning") == HazardType.FLOOD
    assert HazardType.from_str("Severe Thunderstorm") == HazardType.SEVERE_STORM
    assert HazardType.from_str("Tropical Cyclone Jasper") == HazardType.CYCLONE
    assert HazardType.from_str("Tsunami Warning") == HazardType.TSUNAMI
    assert HazardType.from_str("Volcano Activity") == HazardType.VOLCANO
    assert HazardType.from_str("Volcanic ash cloud") == HazardType.VOLCANO
    assert HazardType.from_str("Ash plume") == HazardType.VOLCANO
    assert HazardType.from_str("Car crash") == HazardType.ROAD_INCIDENT
    assert HazardType.from_str("Trash fire") == HazardType.BUSHFIRE
    assert HazardType.from_str("Earthquake tremor") == HazardType.EARTHQUAKE
    assert HazardType.from_str("Chemical Hazmat spill") == HazardType.HAZMAT
    assert HazardType.from_str("Road closed hazard") == HazardType.ROAD_INCIDENT
    assert HazardType.from_str("Kitchen fire") == HazardType.BUSHFIRE
    assert HazardType.from_str("Unspecified event") == HazardType.OTHER
    assert HazardType.from_str(None) == HazardType.OTHER


def test_canonical_hazard_safe_attributes() -> None:
    """Test that CanonicalHazard produces safe scalar attributes under SQLite 16 KB limit."""
    huge_polygon_coords = [[[153.0 + i * 0.001, -27.0 + i * 0.001] for i in range(1000)]]
    hazard = CanonicalHazard(
        id="TEST_123",
        source="QFD",
        title="Test Incident",
        hazard_type=HazardType.BUSHFIRE,
        warning_level=WarningLevel.EMERGENCY_WARNING,
        latitude=-27.26,
        longitude=152.98,
        updated_at=datetime(2026, 10, 15, 1, 0, 0, tzinfo=UTC),
        location_name="Moreton Bay",
        distance_km=14.5678,
        is_hazard_reduction=False,
        status="Going",
        responsible_agency="Rural Fire Service",
        web_url="https://example.com/warning",
        raw_properties={
            "huge_geometry_polygon": huge_polygon_coords,  # Massive list
            "safe_string": "Small Note",
            "safe_number": 42,
        },
    )

    assert hazard.is_active_threat is True
    attrs = hazard.to_safe_attributes()

    # Verify massive polygon coordinates were stripped out
    assert "huge_geometry_polygon" not in attrs
    assert "prop_huge_geometry_polygon" not in attrs

    # Verify safe fields are preserved
    assert attrs["integration"] == "ausnz_disaster_watch"
    assert attrs["source"] == "QFD"
    assert attrs["title"] == "Test Incident"
    assert attrs["hazard_type"] == "Bushfire"
    assert attrs["warning_level"] == "Emergency Warning"
    assert attrs["distance_km"] == 14.57
    assert attrs["location_name"] == "Moreton Bay"
    assert attrs["status"] == "Going"
    assert attrs["responsible_agency"] == "Rural Fire Service"
    assert attrs["prop_safe_string"] == "Small Note"
    assert attrs["prop_safe_number"] == 42

    # String representation of attributes must be under 1 KB, well below 16 KB
    assert len(str(attrs)) < 1024


def test_canonical_hazard_minimal_safe_attributes() -> None:
    """Test CanonicalHazard to_safe_attributes when optional attributes are None."""
    hazard = CanonicalHazard(
        id="TEST_MIN",
        source="TEST",
        title="Minimal Incident",
        hazard_type=HazardType.OTHER,
        warning_level=WarningLevel.UNKNOWN,
        latitude=-27.0,
        longitude=153.0,
        updated_at=datetime.now(UTC),
    )
    attrs = hazard.to_safe_attributes()
    assert "distance_km" not in attrs
    assert "status" not in attrs
    assert "responsible_agency" not in attrs
    assert "web_url" not in attrs


def test_canonical_hazard_datetime_validator() -> None:
    """Test updated_at field validator with diverse input types."""
    # ISO string with Z
    h1 = CanonicalHazard(
        id="1",
        source="s",
        title="t",
        hazard_type=HazardType.BUSHFIRE,
        warning_level=WarningLevel.ADVICE,
        latitude=-25.0,
        longitude=150.0,
        updated_at="2026-10-15T05:30:00Z",  # type: ignore[arg-type]
    )
    assert h1.updated_at.tzinfo is not None

    # Timezone-naive datetime gets UTC
    dt_naive = datetime(2026, 10, 15, 5, 30)
    h2 = CanonicalHazard(
        id="2",
        source="s",
        title="t",
        hazard_type=HazardType.BUSHFIRE,
        warning_level=WarningLevel.ADVICE,
        latitude=-25.0,
        longitude=150.0,
        updated_at=dt_naive,
    )
    assert h2.updated_at.tzinfo == UTC

    # Unknown/unsupported values stay None instead of pretending to be "now" (#13)
    h3 = CanonicalHazard(
        id="3",
        source="s",
        title="t",
        hazard_type=HazardType.BUSHFIRE,
        warning_level=WarningLevel.ADVICE,
        latitude=-25.0,
        longitude=150.0,
        updated_at=12345,  # type: ignore[arg-type]
    )
    assert h3.updated_at is None
    assert "updated_at" not in h3.to_safe_attributes()

    # An invalid ISO string is an unknown time, not a rejected hazard
    h5 = CanonicalHazard(
        id="5",
        source="s",
        title="t",
        hazard_type=HazardType.BUSHFIRE,
        warning_level=WarningLevel.ADVICE,
        latitude=-25.0,
        longitude=150.0,
        updated_at="not a timestamp",  # type: ignore[arg-type]
    )
    assert h5.updated_at is None

    # Aware non-UTC values are normalised to UTC
    h4 = CanonicalHazard(
        id="4",
        source="s",
        title="t",
        hazard_type=HazardType.BUSHFIRE,
        warning_level=WarningLevel.ADVICE,
        latitude=-25.0,
        longitude=150.0,
        updated_at="2026-10-15T15:30:00+10:00",  # type: ignore[arg-type]
    )
    assert h4.updated_at == datetime(2026, 10, 15, 5, 30, tzinfo=UTC)
    assert h4.to_safe_attributes()["updated_at"] == "2026-10-15T05:30:00+00:00"


def test_disaster_watch_config_model() -> None:
    """Test DisasterWatchConfigModel validation and defaults."""
    model = DisasterWatchConfigModel()
    assert model.state == "QLD"
    assert model.radius == 50
    assert model.override_emergency is True
    assert model.exclude_hazard_reduction is True
    assert model.location_mode == "home"

    custom = DisasterWatchConfigModel(
        state="NSW",
        radius=100,
        latitude=-33.86,
        longitude=151.21,
        location_name="Sydney",
        council_dashboard_url="https://example.com",
    )
    assert custom.state == "NSW"
    assert custom.radius == 100
    assert custom.latitude == -33.86
    assert custom.longitude == 151.21
    assert custom.location_name == "Sydney"
    assert custom.council_dashboard_url == "https://example.com"


def test_canonical_hazard_conflicting_raw_property() -> None:
    """Test to_safe_attributes skips raw properties matching existing attributes."""
    hazard = CanonicalHazard(
        id="TEST_DUP",
        source="TEST",
        title="Incident",
        hazard_type=HazardType.BUSHFIRE,
        warning_level=WarningLevel.ADVICE,
        latitude=-27.0,
        longitude=153.0,
        updated_at=datetime.now(UTC),
        raw_properties={"title": "Raw Title", "custom_key": "val"},
    )
    attrs = hazard.to_safe_attributes()
    assert attrs["title"] == "Incident"
    assert "prop_title" not in attrs
    assert attrs["prop_custom_key"] == "val"


def test_disaster_coordinator_data_mapping() -> None:
    """Test DisasterCoordinatorData mapping protocol methods."""
    hazard = CanonicalHazard(
        id="h1",
        source="TEST",
        title="Incident 1",
        hazard_type=HazardType.BUSHFIRE,
        warning_level=WarningLevel.ADVICE,
        latitude=-27.0,
        longitude=153.0,
        updated_at=datetime.now(UTC),
    )
    coord_data = DisasterCoordinatorData(hazards={"h1": hazard})

    assert len(coord_data) == 1
    assert bool(coord_data) is True
    assert "h1" in coord_data
    assert "missing" not in coord_data
    assert coord_data["h1"] == hazard
    assert coord_data.get("h1") == hazard
    assert coord_data.get("missing") is None
    assert coord_data.get("missing", 42) == 42

    empty_data = DisasterCoordinatorData()
    assert len(empty_data) == 0
    assert bool(empty_data) is True


def _hazard(**overrides: Any) -> CanonicalHazard:
    values: dict[str, Any] = {
        "id": "h1",
        "source": "TEST",
        "title": "Incident",
        "hazard_type": HazardType.BUSHFIRE,
        "warning_level": WarningLevel.ADVICE,
        "latitude": -27.0,
        "longitude": 153.0,
    } | overrides
    return CanonicalHazard(**values)


def test_models_convert_values_like_the_pydantic_models() -> None:
    """Lenient conversions providers relied on still happen when a model is created (#20)."""
    hazard = _hazard(
        hazard_type="Flood", warning_level="Watch and Act", latitude=-27, longitude="153.5", title=HazardType.FLOOD
    )
    assert hazard.hazard_type is HazardType.FLOOD
    assert hazard.warning_level is WarningLevel.WATCH_AND_ACT
    assert (hazard.latitude, hazard.longitude) == (-27.0, 153.5)
    assert type(hazard.latitude) is float
    assert type(hazard.title) is str  # a StrEnum member is stored as its value
    assert _hazard(is_hazard_reduction="yes").is_hazard_reduction is True
    assert _hazard(is_hazard_reduction=0).is_hazard_reduction is False
    assert _hazard(inside_area="Off").inside_area is False
    assert _hazard(area=[[(-27, 153), ("-27.1", 153.1)]]).area == (((-27.0, 153.0), (-27.1, 153.1)),)

    assert PowerOutageItem(customers_affected="12").customers_affected == 12
    assert PowerOutageItem(customers_affected=3.0).customers_affected == 3
    assert PowerOutageItem(customers_affected=" 4.0 ").customers_affected == 4
    assert PowerOutageItem(customers_affected=Decimal(5)).customers_affected == 5

    stamp = datetime(2023, 11, 14, 22, 13, 20, tzinfo=UTC)
    assert TsunamiStatus(active=True, source="s", issued=1700000000).issued == stamp
    assert TsunamiStatus(active=True, source="s", issued="1700000000").issued == stamp
    assert TsunamiStatus(active=True, source="s", issued="2026-10-15T05:30:00Z").issued == datetime(
        2026, 10, 15, 5, 30, tzinfo=UTC
    )
    assert TsunamiStatus(active=1, source="s", products=("a",)).products == ["a"]

    # Nested models may be given as dicts; dates as text or a midnight datetime
    outlook = FireDangerOutlook(
        district_number="NSW_FW008",
        district_name="Greater Sydney",
        time_zone="Australia/Sydney",
        source="BoM",
        days=[{"date": "2026-10-15", "rating": "High"}, FireDangerDay(date=datetime(2026, 10, 16))],
    )
    assert [day.date for day in outlook.days] == [date(2026, 10, 15), date(2026, 10, 16)]
    assert DisasterCoordinatorData(fire_danger={"rating": "High"}).fire_danger == FireDangerRating(rating="High")


def test_models_copy_containers() -> None:
    """A model holds its own copy of a list or dict, as the pydantic models did."""
    raw: dict[str, Any] = {"a": 1}
    hazard = _hazard(raw_properties=raw)
    raw["b"] = 2
    assert hazard.raw_properties == {"a": 1}
    outages: list[PowerOutageItem] = []
    data = DisasterCoordinatorData(power_outages=outages)
    outages.append(PowerOutageItem())
    assert data.power_outages == []


@pytest.mark.parametrize(
    ("factory", "field"),
    [
        (lambda: _hazard(latitude=91.0), "latitude"),
        (lambda: _hazard(longitude=-180.5), "longitude"),
        (lambda: _hazard(distance_km=-1.0), "distance_km"),
        (lambda: _hazard(latitude=float("nan")), "latitude"),
        (lambda: _hazard(latitude="north"), "latitude"),
        (lambda: _hazard(latitude=None), "latitude"),
        (lambda: _hazard(title=None), "title"),
        (lambda: _hazard(title=5), "title"),
        (lambda: _hazard(warning_level="Extreme"), "warning_level"),
        (lambda: _hazard(is_hazard_reduction="maybe"), "is_hazard_reduction"),
        (lambda: _hazard(is_hazard_reduction=2), "is_hazard_reduction"),
        (lambda: _hazard(inside_area=" off"), "inside_area"),
        (lambda: _hazard(raw_properties=[1]), "raw_properties"),
        (lambda: PowerOutageItem(customers_affected=2.5), "customers_affected"),
        (lambda: PowerOutageItem(customers_affected="many"), "customers_affected"),
        (lambda: PowerOutageItem(customers_affected=[1]), "customers_affected"),
        (lambda: PowerOutageItem(customers_affected=-1), "customers_affected"),
        (lambda: PowerOutageItem(latitude=object()), "latitude"),
        (lambda: TsunamiStatus(active=True, source="s", issued="soon"), "issued"),
        (lambda: TsunamiStatus(active=True, source="s", issued=float("inf")), "issued"),
        (lambda: TsunamiStatus(active=True, source="s", issued=[2026]), "issued"),
        (lambda: TsunamiStatus(active=True, source="s", products="a"), "products"),
        (lambda: FireDangerDay(date=datetime(2026, 10, 15, 1)), "date"),
        (lambda: FireDangerDay(date=20261015), "date"),
        (lambda: FireDangerDay(date="15/10/2026"), "date"),
        (lambda: DisasterCoordinatorData(fire_danger="High"), "fire_danger"),
        (lambda: DisasterCoordinatorData(hazards={"h1": {"id": "h1"}}), "hazards"),
        (lambda: DisasterWatchConfigModel(state="qld"), "state"),
        (lambda: DisasterWatchConfigModel(radius=301), "radius"),
    ],
)
def test_models_reject_wrong_values(factory: Callable[[], Any], field: str) -> None:
    """A value of the wrong type or out of range raises a ValueError naming the field (#16)."""
    with pytest.raises(ModelValidationError, match=rf"\.{field}: ") as err:
        factory()
    assert isinstance(err.value, ValueError)  # providers skip the record (MALFORMED_ITEM_ERRORS)


def test_unsupported_field_type() -> None:
    """A field type the models do not convert is a programming error found at import."""
    with pytest.raises(TypeError, match="Unsupported model field type"):
        models._converter_for(set[int])
    assert models._converter_for(Any) is None  # any value is accepted
    assert models._optional(None) is None


def test_frozen_models_cannot_change() -> None:
    """Models nothing updates after creation are frozen; replace() makes a changed copy."""
    outage = PowerOutageItem(id="1")
    with pytest.raises(FrozenInstanceError):
        outage.id = "2"  # type: ignore[misc]
    assert replace(outage, id="2").id == "2"


def test_config_model_from_config() -> None:
    """Entry data and options are validated; keys the model does not read are ignored."""
    cfg = DisasterWatchConfigModel.from_config({"state": "NSW", "radius": "100", "unrelated": object()})
    assert (cfg.state, cfg.radius) == ("NSW", 100)
    with pytest.raises(ModelValidationError, match="radius"):
        DisasterWatchConfigModel.from_config({"radius": 4})


def test_json_and_python_dumps() -> None:
    """to_json_dict writes what pydantic's JSON mode wrote; to_dict keeps Python values (#20)."""
    issued = datetime(2026, 10, 15, 5, 30, 1, 120000, tzinfo=UTC)
    hazard = _hazard(
        updated_at=issued,
        area=(((-27.0, 153.0),),),
        raw_properties={"nested": {"when": issued, "kind": HazardType.FLOOD, "pair": (1, 2)}, HazardType.FLOOD: 1},
    )
    as_json = to_json_dict(hazard)
    assert list(as_json) == [f.name for f in fields(CanonicalHazard) if f.name != "area"]
    assert as_json["hazard_type"] == "Bushfire"
    assert as_json["updated_at"] == "2026-10-15T05:30:01.120000Z"
    assert as_json["raw_properties"] == {
        "nested": {"when": "2026-10-15T05:30:01.120000Z", "kind": "Flood", "pair": [1, 2]},
        "Flood": 1,
    }
    as_python = to_dict(hazard)
    assert "area" not in as_python
    assert as_python["hazard_type"] is HazardType.BUSHFIRE
    assert as_python["updated_at"] is issued
    assert as_python["raw_properties"]["nested"]["pair"] == (1, 2)

    brisbane = timezone(timedelta(hours=10))
    status = TsunamiStatus(active=False, source="JATWC", issued=datetime(2026, 10, 15, 15, 30, tzinfo=brisbane))
    assert to_json_dict(status)["issued"] == "2026-10-15T15:30:00+10:00"
    assert to_json_dict(FireDangerDay(date=date(2026, 10, 15)))["date"] == "2026-10-15"
    heatwave = HeatwaveStatus(severity="none", product_id="p", areas=[HeatwaveArea(name="a", severity="low")])
    assert to_json_dict(heatwave)["areas"] == [{"name": "a", "severity": "low"}]
    assert to_json_dict(DisasterCoordinatorData(nearby_councils=[{"name": "x"}]))["nearby_councils"] == [{"name": "x"}]
    assert to_json_dict(FireSeasonStatus(last_updated=datetime(2026, 1, 1, 12, tzinfo=UTC)))["last_updated"] == (
        "2026-01-01T12:00:00Z"
    )
    assert to_dict(UVObservation(station_id="b", station_name="Brisbane", index=3))["index"] == 3.0
    assert models._dump(dt.time(5, 30), json_mode=True) == "05:30:00"
