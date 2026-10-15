"""Unit tests for models, enums and CanonicalHazard."""

from datetime import UTC, datetime

from custom_components.australian_disaster_watch.models import (
    CanonicalHazard,
    DisasterWatchConfigModel,
    HazardType,
    WarningLevel,
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
    assert HazardType.from_str("Tsunami Warning") == HazardType.EARTHQUAKE
    assert HazardType.from_str("Chemical Hazmat spill") == HazardType.HAZMAT
    assert HazardType.from_str("Road closed hazard") == HazardType.ROAD_INCIDENT
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

    # Non-string/non-datetime fallback to now(UTC)
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
    assert h3.updated_at.tzinfo == UTC


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
