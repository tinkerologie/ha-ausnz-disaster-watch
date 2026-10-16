"""Core data models and contracts for Australian Disaster Watch (standard-library dataclasses, #20).

Every model checks its fields when it is created, as the pydantic models did before: a value of
the wrong type or out of range raises ``ModelValidationError`` (a ``ValueError``, so providers
skip that one record, #16), and the lenient conversions providers relied on still happen (an
``int`` for a ``float`` field, a numeric string, an enum value, an ISO 8601 timestamp). Each
class's checks are planned once, from its type hints, when this module is imported.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
import dataclasses
from dataclasses import dataclass, field
import datetime as dt
from datetime import UTC, datetime
from decimal import Decimal
from enum import Enum, StrEnum
import re
import types
from typing import Any, Union, cast, get_args, get_origin, get_type_hints

# Longest call to action written to state attributes
CALL_TO_ACTION_MAX_LENGTH = 255
# Upstream editor fields (ArcGIS ``created_user``/``last_edited_user`` hold email addresses)
_PERSONAL_KEYS = frozenset({"created_user", "last_edited_user", "creator", "editor"})


def _is_personal_key(key: str) -> bool:
    """Return True for raw property keys that may identify a person (never copied to attributes)."""
    lowered = key.lower()
    return lowered in _PERSONAL_KEYS or "email" in lowered


class ModelValidationError(ValueError):
    """A model field got a value of the wrong type or out of range."""


type _Converter = Callable[[Any], Any]
type _Bounds = tuple[float | None, float | None, re.Pattern[str] | None]

# Field metadata keys
_BOUNDS = "bounds"
_COERCE = "coerce"
_EXCLUDE = "exclude"


def _bounds(*, ge: float | None = None, le: float | None = None, pattern: re.Pattern[str] | None = None) -> dict:
    """Field metadata: the value (when not None) must lie in [ge, le] or match the pattern."""
    return {_BOUNDS: (ge, le, pattern)}


def _coerce(converter: _Converter) -> dict:
    """Field metadata: convert the raw value with ``converter`` instead of by the type hint."""
    return {_COERCE: converter}


_EXCLUDED = {_EXCLUDE: True}  # never written to state attributes or diagnostics
_LATITUDE = _bounds(ge=-90.0, le=90.0)
_LONGITUDE = _bounds(ge=-180.0, le=180.0)
_NON_NEGATIVE = _bounds(ge=0.0)

_TRUE_STRINGS = frozenset({"1", "on", "t", "true", "y", "yes"})
_FALSE_STRINGS = frozenset({"0", "off", "f", "false", "n", "no"})


def _to_str(value: Any) -> str:
    if not isinstance(value, str):
        raise TypeError(f"expected a string, got {type(value).__name__}")
    # A StrEnum member is stored as its plain value
    return str(value.value) if isinstance(value, Enum) else value


def _to_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and value in (0, 1):
        return bool(value)
    if isinstance(value, str):
        text = value.lower()  # case-insensitive, but surrounding spaces are rejected like before
        if text in _TRUE_STRINGS:
            return True
        if text in _FALSE_STRINGS:
            return False
    raise ValueError(f"expected a boolean, got {value!r}")


def _to_int(value: Any) -> int:
    if isinstance(value, int):
        return int(value)  # a bool becomes 0 or 1
    if isinstance(value, str):
        try:
            return int(value.strip())
        except ValueError:
            value = float(value)
    if isinstance(value, (float, Decimal)):
        if value != int(value):
            raise ValueError(f"expected a whole number, got {value!r}")
        return int(value)
    raise TypeError(f"expected an integer, got {type(value).__name__}")


def _to_float(value: Any) -> float:
    if isinstance(value, float):
        return value
    if isinstance(value, (int, str, Decimal)):
        return float(value)
    raise TypeError(f"expected a number, got {type(value).__name__}")


def _to_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            value = float(value)  # a Unix timestamp as text
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return datetime.fromtimestamp(value, UTC)
    raise TypeError(f"expected a datetime, got {type(value).__name__}")


def _to_date(value: Any) -> dt.date:
    if isinstance(value, datetime):
        if value.time() != dt.time():
            raise ValueError(f"expected a date, got a datetime with a time: {value!r}")
        return value.date()
    if isinstance(value, dt.date):
        return value
    if isinstance(value, str):
        return dt.date.fromisoformat(value)
    raise TypeError(f"expected a date, got {type(value).__name__}")


_SIMPLE_CONVERTERS: dict[Any, _Converter] = {
    str: _to_str,
    bool: _to_bool,
    int: _to_int,
    float: _to_float,
    datetime: _to_datetime,
    dt.date: _to_date,
}


def _utc_or_none(value: Any) -> datetime | None:
    """Normalise a timestamp to an aware UTC datetime; unknown times stay None (#13)."""
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value)
        except ValueError:
            return None
    if isinstance(value, datetime):
        return (value if value.tzinfo else value.replace(tzinfo=UTC)).astimezone(UTC)
    return None


def _blank_is_none(value: Any) -> str | None:
    """Treat a blank or whitespace-only key as no key."""
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _area(value: Any) -> tuple[tuple[tuple[float, float], ...], ...] | None:
    """Keep an area built by the geometry helpers; convert rings given as lists."""
    if value is None or isinstance(value, tuple):
        return value
    return tuple(tuple((float(lat), float(lon)) for lat, lon in ring) for ring in value)


def _optional(convert: _Converter | None) -> _Converter | None:
    if convert is None:
        return None
    return lambda value: None if value is None else convert(value)


def _list_of(convert: _Converter | None) -> _Converter:
    def to_list(value: Any) -> list[Any]:
        if not isinstance(value, (list, tuple)):
            raise TypeError(f"expected a list, got {type(value).__name__}")
        return list(value) if convert is None else [convert(item) for item in value]

    return to_list


def _dict_of(convert: _Converter | None) -> _Converter:
    def to_dict(value: Any) -> dict[Any, Any]:
        if not isinstance(value, Mapping):
            raise TypeError(f"expected a dict, got {type(value).__name__}")
        return dict(value) if convert is None else {key: convert(item) for key, item in value.items()}

    return to_dict


def _instance_of(cls: type) -> _Converter:
    def to_instance(value: Any) -> Any:
        if isinstance(value, cls):
            return value
        if isinstance(value, Mapping):
            return cls(**value)
        raise TypeError(f"expected {cls.__name__}, got {type(value).__name__}")

    return to_instance


def _enum_member(cls: type[Enum]) -> _Converter:
    return lambda value: value if isinstance(value, cls) else cls(value)


def _converter_for(hint: Any) -> _Converter | None:
    """Return the converter for a field type hint, or None when any value is accepted."""
    if hint is Any:
        return None
    origin = get_origin(hint)
    if origin in (Union, types.UnionType):
        (inner,) = (arg for arg in get_args(hint) if arg is not type(None))  # only ``X | None`` is used
        return _optional(_converter_for(inner))
    if origin is list:
        return _list_of(_converter_for(get_args(hint)[0]))
    if origin is dict:
        return _dict_of(_converter_for(get_args(hint)[1]))
    if isinstance(hint, type) and issubclass(hint, Enum):
        return _enum_member(hint)
    if dataclasses.is_dataclass(hint):
        return _instance_of(cast("type", hint))
    if hint in _SIMPLE_CONVERTERS:
        return _SIMPLE_CONVERTERS[hint]
    raise TypeError(f"Unsupported model field type: {hint!r}")


def _check_bounds(value: Any, bounds: _Bounds) -> None:
    ge, le, pattern = bounds
    if value is None:
        return
    if ge is not None and not value >= ge:
        raise ValueError(f"{value!r} is less than {ge}")
    if le is not None and not value <= le:
        raise ValueError(f"{value!r} is greater than {le}")
    if pattern is not None and not pattern.search(value):
        raise ValueError(f"{value!r} does not match {pattern.pattern}")


type _Plan = tuple[tuple[str, _Converter | None, _Bounds | None], ...]
_PLANS: dict[type, _Plan] = {}


def _plan(cls: type) -> _Plan:
    """Return (field, converter, bounds) for each checked field of a model class, built once."""
    plan = _PLANS.get(cls)
    if plan is None:
        hints = get_type_hints(cls)
        steps = []
        for model_field in dataclasses.fields(cls):
            convert = model_field.metadata.get(_COERCE) or _converter_for(hints[model_field.name])
            bounds = model_field.metadata.get(_BOUNDS)
            if convert is not None or bounds is not None:
                steps.append((model_field.name, convert, bounds))
        plan = _PLANS[cls] = tuple(steps)
    return plan


def _validate(model: Any) -> None:
    """Convert and check every field of a freshly created model in place."""
    for name, convert, bounds in _plan(type(model)):
        value = getattr(model, name)
        try:
            if convert is not None:
                converted = convert(value)
                if converted is not value:
                    object.__setattr__(model, name, converted)  # frozen models too
                value = converted
            if bounds is not None:
                _check_bounds(value, bounds)
        except (TypeError, ValueError, ArithmeticError, OSError) as err:
            raise ModelValidationError(f"{type(model).__name__}.{name}: {err}") from err


class _Model:
    """Base of every model: converts and checks the fields once ``__init__`` has set them."""

    __slots__ = ()

    def __post_init__(self) -> None:
        """Validate the fields."""
        _validate(self)


def _isoformat(value: datetime) -> str:
    """Format like pydantic's JSON mode did: a zero UTC offset is written as ``Z``."""
    text = value.isoformat()
    if value.utcoffset() == dt.timedelta(0) and text.endswith("+00:00"):
        return text[: -len("+00:00")] + "Z"
    return text


def _dump(value: Any, json_mode: bool) -> Any:
    if isinstance(value, _Model):
        return {
            model_field.name: _dump(getattr(value, model_field.name), json_mode)
            for model_field in dataclasses.fields(cast("Any", value))
            if not model_field.metadata.get(_EXCLUDE)
        }
    if isinstance(value, dict):
        return {(_dump(key, json_mode) if json_mode else key): _dump(item, json_mode) for key, item in value.items()}
    if isinstance(value, list):
        return [_dump(item, json_mode) for item in value]
    if isinstance(value, tuple):
        items = [_dump(item, json_mode) for item in value]
        return items if json_mode else tuple(items)
    if json_mode:
        if isinstance(value, Enum):
            return value.value
        if isinstance(value, datetime):
            return _isoformat(value)
        if isinstance(value, (dt.date, dt.time)):
            return value.isoformat()
    return value


def to_dict(model: _Model) -> dict[str, Any]:
    """Return a model's fields (nested models as dicts), leaving out area geometry."""
    return _dump(model, json_mode=False)


def to_json_dict(model: _Model) -> dict[str, Any]:
    """Return a model's fields as JSON-safe values: enums as values, times as ISO 8601 text."""
    return _dump(model, json_mode=True)


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
    VOLCANO = "Volcano"
    TSUNAMI = "Tsunami"
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
        if any(word in val for word in ("storm", "thunder", "rain", "hail", "wind", "severe weather")):
            return cls.SEVERE_STORM
        if "volcan" in val or re.search(r"\bash(fall| fall| cloud| plume)?\b", val):
            return cls.VOLCANO
        if "tsunami" in val:
            return cls.TSUNAMI
        if "earthquake" in val or "tremor" in val:
            return cls.EARTHQUAKE
        if "hazmat" in val or "chemical" in val or "gas" in val:
            return cls.HAZMAT
        if "road" in val or "crash" in val or "traffic" in val or "closure" in val:
            return cls.ROAD_INCIDENT
        if "fire" in val:
            return cls.BUSHFIRE
        return cls.OTHER


@dataclass(slots=True, kw_only=True)
class CanonicalHazard(_Model):
    """Canonical representation of an emergency hazard incident or warning."""

    id: str  # Globally unique hazard identifier
    source: str  # Source agency or feed identifier
    title: str  # Descriptive headline
    hazard_type: HazardType  # Normalized hazard classification
    warning_level: WarningLevel  # Normalized Australian Warning System level
    latitude: float = field(metadata=_LATITUDE)  # Centroid latitude in degrees
    longitude: float = field(metadata=_LONGITUDE)  # Centroid longitude in degrees
    # Timezone-aware UTC timestamp of last update; None when the feed gives no usable time (#13)
    updated_at: datetime | None = field(default=None, metadata=_coerce(_utc_or_none))
    location_name: str = ""  # Locality, suburb, or region name
    # Haversine distance from center coordinates in km
    distance_km: float | None = field(default=None, metadata=_NON_NEGATIVE)
    is_hazard_reduction: bool = False  # Flag indicating planned/controlled burn
    status: str | None = None  # Operational status (e.g. Going, Safe)
    responsible_agency: str | None = None  # Responsible operational authority
    web_url: str | None = None  # Direct URL to official emergency alert document
    raw_properties: dict[str, Any] = field(default_factory=dict)  # Raw upstream properties preserved for inspection
    attribution: str | None = None  # Data source attribution; the coordinator fills it from the provider (#34)
    # Simplified warning or incident area: outer rings of (lat, lon) points (#30).
    # Never written to state attributes or diagnostics.
    area: tuple[tuple[tuple[float, float], ...], ...] | None = field(
        default=None, metadata={**_EXCLUDED, **_coerce(_area)}, repr=False
    )
    inside_area: bool | None = None  # True if the monitored point is inside ``area``; None without an area
    # Timezone-aware UTC time the warning expires
    expires: datetime | None = field(default=None, metadata=_coerce(_utc_or_none))
    call_to_action: str | None = None  # Australian Warning System call to action

    @property
    def is_active_threat(self) -> bool:
        """Return True if hazard is an emergency warning or watch and act."""
        return self.warning_level in (
            WarningLevel.EMERGENCY_WARNING,
            WarningLevel.WATCH_AND_ACT,
        )

    @property
    def is_inside_warning(self) -> bool:
        """Return True if the monitored point is inside the area of an Advice or higher warning (#30)."""
        return self.inside_area is True and self.warning_level.severity_rank >= WarningLevel.ADVICE.severity_rank

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
            "is_hazard_reduction": self.is_hazard_reduction,
            "integration": "ausnz_disaster_watch",
        }
        if self.updated_at is not None:
            attrs["updated_at"] = self.updated_at.isoformat()
        if self.distance_km is not None:
            attrs["distance_km"] = round(self.distance_km, 2)
        if self.status:
            attrs["status"] = self.status
        if self.responsible_agency:
            attrs["responsible_agency"] = self.responsible_agency
        if self.web_url:
            attrs["web_url"] = self.web_url
        if self.inside_area is not None:
            attrs["inside_area"] = self.inside_area
        if self.expires is not None:
            attrs["expires"] = self.expires.isoformat()
        if self.call_to_action:
            attrs["call_to_action"] = self.call_to_action[:CALL_TO_ACTION_MAX_LENGTH]

        # Selectively copy small safe primitive properties from raw_properties
        for k, v in self.raw_properties.items():
            if k in attrs or _is_personal_key(k):
                continue
            if isinstance(v, (str, int, float, bool)) and len(str(v)) < 120:
                attrs[f"prop_{k}"] = v

        return attrs


@dataclass(slots=True, kw_only=True, frozen=True)
class DisasterWatchConfigModel(_Model):
    """Validated configuration entry parameters (defaults for keys an entry does not have)."""

    state: str = field(default="QLD", metadata=_bounds(pattern=re.compile(r"^[A-Z]{2,3}$")))
    radius: int = field(default=50, metadata=_bounds(ge=5, le=300))
    override_emergency: bool = True
    exclude_hazard_reduction: bool = True
    location_mode: str = "home"
    latitude: float | None = field(default=None, metadata=_LATITUDE)
    longitude: float | None = field(default=None, metadata=_LONGITUDE)
    location_name: str | None = None
    council_dashboard_url: str | None = None
    include_roadworks: bool = False
    vic_api_key: str | None = field(default=None, metadata=_coerce(_blank_is_none))

    include_planned_outages: bool = False
    extra_outage_feeds: bool = False

    @classmethod
    def from_config(cls, config: Mapping[str, Any]) -> DisasterWatchConfigModel:
        """Validate merged entry data and options, ignoring keys this model does not read.

        Raises ModelValidationError (a ValueError) for a value of the wrong type or out of range.
        """
        names = {model_field.name for model_field in dataclasses.fields(cls)}
        return cls(**{key: value for key, value in config.items() if key in names})


@dataclass(slots=True, kw_only=True, frozen=True)
class PowerOutageItem(_Model):
    """Real-time power outage item from energy network feeds (e.g. Energex, Ergon, Ausgrid)."""

    suburb: str = ""  # Locality or suburb name
    cause: str = "Under Investigation"  # Reported cause of outage
    restore_time: str | None = None  # Estimated time of restoration
    customers_affected: int = field(default=0, metadata=_NON_NEGATIVE)  # Number of customers affected
    latitude: float | None = field(default=None, metadata=_LATITUDE)
    longitude: float | None = field(default=None, metadata=_LONGITUDE)
    # Distributor feeds (#36); council dashboard items leave id and start_time unset
    id: str | None = None  # Distributor incident ID
    distributor: str | None = None  # Electricity distributor (e.g. Energex)
    planned: bool = False  # Planned (maintenance) outage rather than a fault
    status: str | None = None  # Distributor status text
    start_time: str | None = None  # When the outage started (ISO 8601)
    distance_km: float | None = field(default=None, metadata=_NON_NEGATIVE)  # Distance from the monitored point


class RoadEventCategory(StrEnum):
    """What a road event means for someone travelling nearby (#29).

    Planned categories (roadworks, special events) never turn on the "road closure nearby"
    or "flooded road nearby" binary sensors, even when the include-roadworks option lists them.
    """

    FLOODING = "flooding"  # flooded road or crossing, open or closed
    CLOSURE = "closure"  # road closed or impassable (unplanned)
    HAZARD = "hazard"  # unplanned incident or damage on an open road
    ROADWORKS = "roadworks"  # planned roadworks
    SPECIAL_EVENT = "special_event"  # planned special event

    @property
    def is_planned(self) -> bool:
        """Return True for scheduled works and events."""
        return self in (RoadEventCategory.ROADWORKS, RoadEventCategory.SPECIAL_EVENT)

    @classmethod
    def infer(cls, status: str | None, reason: str | None = None) -> RoadEventCategory:
        """Classify an item from its status and reason text (council feeds without a category).

        Precedence is flooding, planned works, closure, then hazard, so a flooded road that
        is also closed reads as flooding.
        """
        status_text = (status or "").lower()
        text = f"{status_text} {(reason or '').lower()}"
        if "flood" in text or "water over" in text:
            return cls.FLOODING
        if "roadwork" in text or re.search(r"\bplanned\b", text):  # not "unplanned"
            return cls.ROADWORKS
        if "special event" in text:
            return cls.SPECIAL_EVENT
        if "closed" in status_text or "closure" in status_text or "impassable" in status_text:
            return cls.CLOSURE
        return cls.HAZARD


@dataclass(slots=True, kw_only=True)
class RoadClosureItem(_Model):
    """Road hazard, closure, or flooded crossing from Council or TMR/LiveTraffic."""

    id: str  # Unique road condition identifier
    road: str = ""  # Road or highway name
    suburb: str = ""  # Suburb or locality
    status: str = "Closed"  # Operational road status (Closed, Hazard, Flooded)
    reason: str | None = None  # Cause (e.g. Flooded, Debris, Crash)
    description: str | None = None  # Detailed condition information
    advice: str | None = None  # Driver advice (e.g. Proceed with caution)
    source: str = "Council / TMR"  # Reporting agency
    updated_at: datetime | None = None  # Timestamp of status update
    latitude: float | None = field(default=None, metadata=_LATITUDE)
    longitude: float | None = field(default=None, metadata=_LONGITUDE)
    distance_km: float | None = field(default=None, metadata=_NON_NEGATIVE)
    # Closure, flooding, hazard, roadworks or special event; inferred from status and reason when unset
    category: RoadEventCategory = cast("RoadEventCategory", None)

    def __post_init__(self) -> None:
        """Derive the category from status and reason when a feed does not set one."""
        if self.category is None:
            # One fallback for a missing and a null status, matching the field default
            self.category = RoadEventCategory.infer(str(self.status or "Closed"), self.reason)
        _validate(self)

    @property
    def is_flooding(self) -> bool:
        """Return True for a flooded road."""
        return self.category == RoadEventCategory.FLOODING

    @property
    def is_planned(self) -> bool:
        """Return True for planned roadworks and special events."""
        return self.category.is_planned


@dataclass(slots=True, kw_only=True, frozen=True)
class WeatherWarningItem(_Model):
    """Bureau of Meteorology weather warning summary from dashboard feed."""

    title: str  # Headline summary of warning
    link: str | None = None  # Direct URL to BoM warning product
    locations: str | None = None  # Affected forecast districts and regions
    pub_date: datetime | None = None  # Publication timestamp


@dataclass(slots=True, kw_only=True, frozen=True)
class EmergencyNewsItem(_Model):
    """Emergency bulletin or media release from Local Disaster Management Group."""

    id: str  # Bulletin identifier
    title: str  # Headline / news title
    description: str | None = None  # Detailed bulletin content
    link: str | None = None  # URL to full media release
    pub_date: datetime | None = None  # Publication timestamp


@dataclass(slots=True, kw_only=True)
class FireDangerRating(_Model):
    """Australian Fire Danger Rating System (AFDRS) regional rating."""

    district_number: str = ""  # Bureau / Agency district code
    district_name: str = ""  # Human-readable district name
    rating: str = "Moderate"  # AFDRS level (Moderate, High, Extreme, Catastrophic)
    total_fire_ban: bool | None = None  # Total Fire Ban in force; None when the feed does not say
    day: str | None = None  # Forecast day


@dataclass(slots=True, kw_only=True)
class FireDangerDay(_Model):
    """One day of a district fire danger forecast, dated in the district's local time (#28)."""

    date: dt.date  # Local calendar day the forecast applies to
    rating: str | None = None  # AFDRS rating (No Rating, Moderate, High, Extreme, Catastrophic)
    fire_behaviour_index: int | None = None  # AFDRS Fire Behaviour Index
    total_fire_ban: bool | None = None  # Total fire ban declared; None when not published
    source: str | None = None  # Agency that supplied this day when the BoM forecast does not cover it (#89)


@dataclass(slots=True, kw_only=True)
class FireDangerOutlook(_Model):
    """Multi-day fire danger forecast and total fire bans for one BoM fire weather district (#28)."""

    district_number: str  # BoM fire weather district AAC (e.g. NSW_FW008)
    district_name: str  # Fire weather district name
    time_zone: str  # IANA time zone the forecast days are dated in
    issued_at: datetime | None = None  # Forecast issue time
    source: str  # Fire danger forecast source
    total_fire_ban_source: str | None = None  # Total fire ban source, if any
    days: list[FireDangerDay] = field(default_factory=list)

    def day(self, on: dt.date) -> FireDangerDay | None:
        """Return the forecast for a local calendar day, if the forecast covers it."""
        return next((day for day in self.days if day.date == on), None)


@dataclass(slots=True, kw_only=True)
class FireSeasonStatus(_Model):
    """New Zealand fire season status and Section 52 prohibitions at a location (#28)."""

    season: str | None = None  # open, restricted or prohibited
    zone: str | None = None  # Fire zone name
    district: str | None = None  # Fire and Emergency NZ district
    last_updated: datetime | None = None
    section_52: bool | None = None  # A Section 52 prohibition covers the location
    section_52_comment: str | None = None
    prohibited_activities: list[str] = field(default_factory=list)


@dataclass(slots=True, kw_only=True, frozen=True)
class WeatherStationObservation(_Model):
    """Local environmental weather station telemetry."""

    station_id: str  # Unique station identifier
    station_name: str  # Station name
    temperature: float | None = None  # Current dry bulb temperature in Celsius
    apparent_temperature: float | None = None  # Feels like temperature in Celsius
    relative_humidity: float | None = field(default=None, metadata=_bounds(ge=0.0, le=100.0))  # Relative humidity in %
    pressure_hpa: float | None = None  # Barometric air pressure in hPa
    # Wind direction vector degrees
    wind_direction: float | None = field(default=None, metadata=_bounds(ge=0.0, le=360.0))
    wind_speed_avg: float | None = field(default=None, metadata=_NON_NEGATIVE)  # Average wind speed in km/h
    wind_speed_max: float | None = field(default=None, metadata=_NON_NEGATIVE)  # Max wind gust in km/h
    rain_since_9am: float | None = field(default=None, metadata=_NON_NEGATIVE)  # Rainfall since 9am in mm
    solar_radiation: float | None = None  # Solar radiation in W/m2


@dataclass(slots=True, kw_only=True)
class AirQualityStationData(_Model):
    """Air quality monitoring station telemetry."""

    station_id: str  # Station identifier
    station_name: str  # Station display name
    pm2_5_measurement: str | None = None  # PM2.5 reading (e.g. '4 µg/m³')
    pm2_5_rating: str | None = None  # PM2.5 rating (Good, Fair, Poor)
    pm2_5_running_average: str | None = None  # PM2.5 24hr running average
    pm10_measurement: str | None = None  # PM10 reading
    pm10_rating: str | None = None  # PM10 rating
    pm10_running_average: str | None = None  # PM10 24hr running average
    no2_measurement: str | None = None  # Nitrogen dioxide reading
    no2_rating: str | None = None  # Nitrogen dioxide rating
    o3_measurement: str | None = None  # Ozone reading
    o3_rating: str | None = None  # Ozone rating
    overall_rating: str | None = "Good"  # Overall station air quality rating; None when no reading is available
    latitude: float | None = field(default=None, metadata=_LATITUDE)
    longitude: float | None = field(default=None, metadata=_LONGITUDE)
    distance_km: float | None = field(default=None, metadata=_NON_NEGATIVE)
    observed_at: datetime | None = None  # Time of the reading
    source: str | None = None  # Agency that published the reading


@dataclass(slots=True, kw_only=True, frozen=True)
class SatelliteHotspotItem(_Model):
    """A satellite-detected heat source (DEA Hotspots). Informational: not a fire or a warning."""

    id: str  # Upstream hotspot identifier
    latitude: float = field(metadata=_LATITUDE)
    longitude: float = field(metadata=_LONGITUDE)
    confidence: float | None = None  # Detection confidence (0-100)
    power: float | None = None  # Fire radiative power in MW, when reported
    temp_kelvin: float | None = None
    hours_since_hotspot: float | None = field(default=None, metadata=_NON_NEGATIVE)
    observed_at: datetime | None = None
    satellite: str | None = None
    distance_km: float | None = field(default=None, metadata=_NON_NEGATIVE)


@dataclass(slots=True, kw_only=True, frozen=True)
class SatelliteHotspots(_Model):
    """Hotspots within the monitoring radius, plus how the query was limited."""

    items: list[SatelliteHotspotItem] = field(default_factory=list)
    min_confidence: float  # Hotspots below this confidence were excluded
    truncated: bool = False  # The upstream query hit its feature limit


@dataclass(slots=True, kw_only=True, frozen=True)
class TsunamiStatus(_Model):
    """Tsunami threat for the configured jurisdiction (JATWC for Australia, PTWC guidance for NZ)."""

    active: bool  # A current tsunami watch or warning applies
    threat_level: str | None = None  # no_threat, watch, marine or land
    headline: str | None = None
    issued: datetime | None = None
    expires: datetime | None = None
    products: list[str] = field(default_factory=list)  # Products present in the last check
    source: str  # Issuing centre
    checked_at: datetime | None = None


@dataclass(slots=True, kw_only=True, frozen=True)
class HeatwaveArea(_Model):
    """One district in a BoM heatwave warning."""

    name: str
    severity: str


@dataclass(slots=True, kw_only=True, frozen=True)
class HeatwaveStatus(_Model):
    """Highest current BoM heatwave warning severity in the configured state."""

    severity: str  # none, low_intensity, severe or extreme
    areas: list[HeatwaveArea] = field(default_factory=list)
    headline: str | None = None
    issued: datetime | None = None
    expires: datetime | None = None
    product_id: str  # BoM product checked


@dataclass(slots=True, kw_only=True, frozen=True)
class UVObservation(_Model):
    """Latest ARPANSA UV index at the nearest monitoring station, with the BoM sun protection forecast."""

    station_id: str
    station_name: str
    index: float = field(metadata=_NON_NEGATIVE)
    observed_at: datetime | None = None
    distance_km: float | None = field(default=None, metadata=_NON_NEGATIVE)
    forecast: str | None = None  # BoM UV alert text for today
    forecast_max_index: int | None = None


@dataclass(slots=True, kw_only=True, frozen=True)
class RegionalAlertItem(_Model):
    """GDACS Orange or Red alert in the Australia/New Zealand region (context only, not a local warning)."""

    id: str
    title: str
    event_type: str | None = None
    alert_level: str
    severity: str | None = None
    country: str | None = None
    latitude: float = field(metadata=_LATITUDE)
    longitude: float = field(metadata=_LONGITUDE)
    from_date: datetime | None = None
    to_date: datetime | None = None
    url: str | None = None
    distance_km: float | None = field(default=None, metadata=_NON_NEGATIVE)
    # GDACS identifiers and the episode geometry the map card draws (#71)
    event_type_code: str | None = None  # GDACS event type code, e.g. 'TC'
    event_id: int | None = None
    episode_id: int | None = None
    geometry_url: str | None = None


@dataclass(slots=True, kw_only=True)
class ReliefFacilityItem(_Model):
    """Disaster relief infrastructure (Sandbag station, Evacuation centre, Place of refuge)."""

    id: str  # Facility unique ID
    facility_type: str  # 'sandbag_station', 'evacuation_centre', or 'place_of_refuge'
    name: str  # Facility name
    suburb: str = ""  # Suburb or locality
    address: str = ""  # Full street address
    status: str = "Open"  # Operational status (Open, Closed)
    latitude: float | None = field(default=None, metadata=_LATITUDE)
    longitude: float | None = field(default=None, metadata=_LONGITUDE)
    distance_km: float | None = field(default=None, metadata=_NON_NEGATIVE)


@dataclass(slots=True, kw_only=True, frozen=True)
class DisasterCameraItem(_Model):
    """Flood or traffic camera feed."""

    id: str  # Camera unique identifier
    name: str  # Camera description or road crossing name
    image_url: str  # Direct URL to live snapshot JPEG/PNG
    suburb: str | None = None  # Locality or suburb
    latitude: float | None = field(default=None, metadata=_LATITUDE)
    longitude: float | None = field(default=None, metadata=_LONGITUDE)
    # Road agency camera networks (#70); council dashboard cameras leave these unset
    source_key: str | None = None  # Data source register key of the camera network
    direction: str | None = None  # Direction the camera faces
    owner: str | None = None  # Who supplies the image, when the network names them
    description: str | None = None  # What the camera shows
    distance_km: float | None = field(default=None, metadata=_NON_NEGATIVE)  # Distance from the monitored location


@dataclass(slots=True, kw_only=True)
class DisasterCoordinatorData(_Model):
    """Composite data structure returned by AustralianDisasterWatchCoordinator."""

    hazards: dict[str, CanonicalHazard] = field(default_factory=dict)
    power_outages: list[PowerOutageItem] = field(default_factory=list)
    road_closures: list[RoadClosureItem] = field(default_factory=list)
    weather_warnings: list[WeatherWarningItem] = field(default_factory=list)
    emergency_news: list[EmergencyNewsItem] = field(default_factory=list)
    fire_danger: FireDangerRating | None = None
    fire_outlook: FireDangerOutlook | None = None
    fire_season: FireSeasonStatus | None = None
    weather_stations: list[WeatherStationObservation] = field(default_factory=list)
    air_quality_stations: list[AirQualityStationData] = field(default_factory=list)
    relief_facilities: list[ReliefFacilityItem] = field(default_factory=list)
    cameras: list[DisasterCameraItem] = field(default_factory=list)
    cameras_failed: list[str] = field(default_factory=list)  # Providers whose camera source failed this update (#92)
    nearby_councils: list[dict[str, str]] = field(default_factory=list)
    feeds_ok: list[str] = field(default_factory=list)  # Hazard providers that fetched successfully
    feeds_failed: list[str] = field(default_factory=list)  # Hazard providers that failed this update
    # Opt-in national feeds (#37). None means "not enabled or could not be determined"; they
    # never enter ``hazards``, so they do not change counts, warning levels or polling.
    satellite_hotspots: SatelliteHotspots | None = None
    tsunami: TsunamiStatus | None = None
    heatwave: HeatwaveStatus | None = None
    uv: UVObservation | None = None
    regional_alerts: list[RegionalAlertItem] | None = None

    def __len__(self) -> int:
        """Return count of active hazards."""
        return len(self.hazards)

    def __bool__(self) -> bool:
        """Always evaluate to True when coordinator data is instantiated."""
        return True

    def __getitem__(self, key: str) -> CanonicalHazard:
        """Access hazard by unique ID."""
        return self.hazards[key]

    def __contains__(self, key: object) -> bool:
        """Check if hazard unique ID exists."""
        return key in self.hazards

    def get(self, key: str, default: Any = None) -> Any:
        """Get hazard by unique ID or fallback."""
        return self.hazards.get(key, default)


# Build every model's field plan at import time, so it resolves the real type hints (a test
# that freezes time replaces ``datetime`` in module namespaces while it runs).
for _model_class in _Model.__subclasses__():
    _plan(_model_class)
