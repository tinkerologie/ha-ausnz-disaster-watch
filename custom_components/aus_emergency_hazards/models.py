"""Core data models and contracts for Australian Emergency Hazards."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any


class WarningLevel(StrEnum):
    """Australian Warning System (AWS) warning levels."""

    EMERGENCY_WARNING = "Emergency Warning"  # AWS Level 3 / Red
    WATCH_AND_ACT = "Watch and Act"  # AWS Level 2 / Orange
    ADVICE = "Advice"  # AWS Level 1 / Yellow
    INFORMATION = "Information"  # General incident / Blue
    UNKNOWN = "Unknown"

    @property
    def severity_rank(self) -> int:
        """Return numeric severity rank for comparison (higher is more critical)."""
        ranks = {
            WarningLevel.EMERGENCY_WARNING: 4,
            WarningLevel.WATCH_AND_ACT: 3,
            WarningLevel.ADVICE: 2,
            WarningLevel.INFORMATION: 1,
            WarningLevel.UNKNOWN: 0,
        }
        return ranks.get(self, 0)

    @classmethod
    def from_str(cls, value: str | None) -> WarningLevel:
        """Parse string representation to WarningLevel."""
        if not value:
            return cls.UNKNOWN
        val = value.strip().lower()
        if "emergency" in val:
            return cls.EMERGENCY_WARNING
        if "watch and act" in val or "watch & act" in val:
            return cls.WATCH_AND_ACT
        if "advice" in val:
            return cls.ADVICE
        if "info" in val or "routine" in val or "notification" in val:
            return cls.INFORMATION
        return cls.UNKNOWN


class HazardType(StrEnum):
    """Hazard classifications."""

    BUSHFIRE = "Bushfire"
    GRASS_FIRE = "Grass Fire"
    METROPOLITAN_FIRE = "Structure Fire"
    FLOOD = "Flood"
    SEVERE_STORM = "Severe Storm"
    CYCLONE = "Tropical Cyclone"
    EARTHQUAKE = "Earthquake"
    HAZMAT = "Hazmat Incident"
    ROAD_INCIDENT = "Road Hazard / Crash"
    OTHER = "Other"

    @classmethod
    def from_str(cls, value: str | None) -> HazardType:
        """Parse string representation to HazardType."""
        if not value:
            return cls.OTHER
        val = value.strip().lower()
        if "bush" in val or "forest" in val or "scrub" in val:
            return cls.BUSHFIRE
        if "grass" in val:
            return cls.GRASS_FIRE
        if "structure" in val or "building" in val or "house" in val:
            return cls.METROPOLITAN_FIRE
        if "flood" in val or "water level" in val or "inundat" in val:
            return cls.FLOOD
        if "cyclone" in val:
            return cls.CYCLONE
        if "storm" in val or "thunder" in val or "rain" in val or "hail" in val or "wind" in val:
            return cls.SEVERE_STORM
        if "earthquake" in val or "tremor" in val or "tsunami" in val:
            return cls.EARTHQUAKE
        if "hazmat" in val or "chemical" in val or "gas" in val:
            return cls.HAZMAT
        if "road" in val or "crash" in val or "traffic" in val or "closure" in val:
            return cls.ROAD_INCIDENT
        if "fire" in val:
            return cls.BUSHFIRE
        return cls.OTHER


@dataclass
class CanonicalHazard:
    """Canonical representation of an emergency hazard incident or warning."""

    id: str  # Globally unique ID (e.g. "QLD_QFD_128945", "NSW_RFS_681307")
    source: str  # Source agency / feed identifier
    title: str  # Descriptive headline
    hazard_type: HazardType
    warning_level: WarningLevel
    latitude: float
    longitude: float
    updated_at: datetime  # UTC aware
    location_name: str
    distance_km: float | None = None
    is_hazard_reduction: bool = False
    status: str | None = None
    responsible_agency: str | None = None
    web_url: str | None = None
    raw_properties: dict[str, Any] = field(default_factory=dict)

    @property
    def is_active_threat(self) -> bool:
        """Return True if hazard is an emergency warning or watch and act."""
        return self.warning_level in (
            WarningLevel.EMERGENCY_WARNING,
            WarningLevel.WATCH_AND_ACT,
        )

    def to_safe_attributes(self) -> dict[str, Any]:
        """Return lean scalar metadata dictionary for Home Assistant state attributes.

        Guarantees that large GeoJSON geometries or heavy nesting are omitted to strictly
        abide by Home Assistant's 16 KB SQLite attribute limit.
        """
        attrs: dict[str, Any] = {
            "source": self.source,
            "title": self.title,
            "hazard_type": self.hazard_type.value,
            "warning_level": self.warning_level.value,
            "location_name": self.location_name,
            "updated_at": self.updated_at.isoformat(),
            "is_hazard_reduction": self.is_hazard_reduction,
        }
        if self.distance_km is not None:
            attrs["distance_km"] = round(self.distance_km, 2)
        if self.status:
            attrs["status"] = self.status
        if self.responsible_agency:
            attrs["responsible_agency"] = self.responsible_agency
        if self.web_url:
            attrs["web_url"] = self.web_url

        # Selectively copy small safe primitive properties from raw_properties
        for k, v in self.raw_properties.items():
            if k in attrs:
                continue
            if isinstance(v, (str, int, float, bool)) and len(str(v)) < 120:
                attrs[f"prop_{k}"] = v

        return attrs
