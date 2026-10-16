"""Queensland emergency hazards provider (QFD & Council Disaster Dashboards)."""

from __future__ import annotations

from dataclasses import dataclass
import logging
import re
from typing import Any

from custom_components.ausnz_disaster_watch.const import CONF_COUNCIL_DASHBOARD_URL, STATE_QLD
from custom_components.ausnz_disaster_watch.council_registry import nearby_council_links
from custom_components.ausnz_disaster_watch.models import (
    AirQualityStationData,
    CanonicalHazard,
    DisasterCameraItem,
    EmergencyNewsItem,
    FireDangerRating,
    HazardType,
    PowerOutageItem,
    ReliefFacilityItem,
    RoadClosureItem,
    WarningLevel,
    WeatherStationObservation,
    WeatherWarningItem,
)

from .base import MALFORMED_ITEM_ERRORS, BaseHazardProvider, ProviderUnavailableError, as_dict, as_float
from .geometry import area_point, rings_from_geojson, simplify_area
from .guardian_ims import GuardianDashboard, normalise_dashboard_url
from .sources import DATA_SOURCES

_LOGGER = logging.getLogger(__name__)

QFD_WARNINGS_URL = (
    "https://publiccontent-gis-psba-qld-gov-au.s3.amazonaws.com"
    "/content/Feeds/BushfireCurrentIncidents/bushfireAlert.json"
)
QFD_WEB_URL = "https://www.fire.qld.gov.au/Current-Incidents"
QLDTRAFFIC_WEB_URL = "https://qldtraffic.qld.gov.au"

_TRAILING_DASH_RE = re.compile(r"\s*-\s*$")


@dataclass(frozen=True, slots=True)
class _WarningAreaLayer:
    """An ArcGIS layer of warning-area polygons (#30)."""

    label: str
    url: str
    # Explicit allowlist: the layers also have editor fields (created_user/last_edited_user)
    # that hold staff email addresses, which are never requested
    fields: tuple[str, ...]
    id_prefix: str
    agency: str
    default_type: HazardType
    web_url: str | None
    source_key: str  # data source register key, for the hazard's attribution


# QFD bushfire warnings (Public Safety Business Agency); the S3 feed has no polygons
_QFD_WARNING_AREAS = _WarningAreaLayer(
    label="QFD warning areas",
    url=("https://services1.arcgis.com/vkTwD8kHw2woKBqV/ArcGIS/rest/services/OCSWarnings_PublicView/FeatureServer/0"),
    fields=(
        "UniqueID",
        "WarningTitle",
        "WarningLevel",
        "WarningArea",
        "CallToAction",
        "MasterIncidentNum",
        "ModifiedDate",
    ),
    id_prefix="QLD_QFD",
    agency="Queensland Fire Department",
    default_type=HazardType.BUSHFIRE,
    web_url=QFD_WEB_URL,
    source_key="qfd_warning_areas",
)
# QPS and council severe weather, flood and cyclone warnings. The matching point layer is
# never read: it exposes editor email addresses
_QPS_WARNING_AREAS = _WarningAreaLayer(
    label="QPS warning areas",
    url=(
        "https://services-ap1.arcgis.com/4z1c8UDtmlbV0cw9/ArcGIS/rest/services"
        "/Severe_Weather_Flood_Cyclone_Area_Public_View/FeatureServer/0"
    ),
    fields=("UniqueID", "WarningTitle", "WarningLevel", "last_edited_date"),
    id_prefix="QLD_QPS",
    agency="Queensland Police Service",
    default_type=HazardType.OTHER,
    web_url=None,
    source_key="qps_warning_areas",
)


def _valid_point(lat: Any, lon: Any) -> tuple[float, float] | None:
    """Return (lat, lon) as floats if they form a real coordinate (not missing, not 0,0)."""
    try:
        flat, flon = float(lat), float(lon)
    except (TypeError, ValueError):
        return None
    if not (-90.0 <= flat <= 90.0 and -180.0 <= flon <= 180.0) or (abs(flat) < 0.001 and abs(flon) < 0.001):
        return None
    return flat, flon


class QueenslandHazardProvider(BaseHazardProvider):
    """Provider for Queensland Fire Department and Local Disaster Dashboards."""

    local_tz = "Australia/Brisbane"

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialise the provider and its council dashboard client, if one is configured."""
        super().__init__(*args, **kwargs)
        base_url = normalise_dashboard_url(self.config.get(CONF_COUNCIL_DASHBOARD_URL))
        self.dashboard: GuardianDashboard | None = GuardianDashboard(self, base_url) if base_url else None

    @property
    def state_code(self) -> str:
        """Return state code."""
        return STATE_QLD

    async def async_fetch_hazards(self) -> list[CanonicalHazard]:
        """Fetch hazards from QFD and optional Council Disaster Dashboard."""
        hazards: list[CanonicalHazard] = []
        seen_ids: set[str] = set()

        # 0. Warning areas (#30): QFD bushfire warnings and QPS severe weather, flood and cyclone
        # warnings as polygons. They come first so a QFD warning also in the S3 feed (same
        # UniqueID, so the same ID) keeps its polygon. A failing layer skips only itself.
        areas_ok = 0
        for layer in (_QFD_WARNING_AREAS, _QPS_WARNING_AREAS):
            try:
                features = await self.async_fetch_arcgis_features(layer.url, "1=1", layer.fields, layer.label)
            except ProviderUnavailableError as err:
                _LOGGER.debug("%s failed: %s", layer.label, err)
                continue
            areas_ok += 1
            for feature in features:
                self._add_parsed(
                    hazards, seen_ids, lambda f, layer=layer: self._parse_warning_area(f, layer), feature, layer.label
                )

        # 1. State-wide QFD Public Warnings feed (primary source)
        qfd_error: str | None = None
        try:
            qfd_data = self.require_dict(await self.async_fetch_feed_json(QFD_WARNINGS_URL, "QFD"), "QFD")
            qfd_features = self.require_list(qfd_data, "features", "QFD")
        except ProviderUnavailableError as err:
            qfd_error = str(err)
            _LOGGER.debug("QFD warnings feed failed: %s", err)
        else:
            for feature in qfd_features:
                self._add_parsed(hazards, seen_ids, self._parse_qfd_feature, feature, "QFD")

        # 2. Council Disaster Dashboard feeds if configured (secondary sources)
        council_ok = 0
        if self.dashboard is not None:
            self.dashboard.start_poll()
            council_hazards, council_ok = await self._fetch_council_hazards(self.dashboard, seen_ids)
            hazards.extend(council_hazards)

        # Unavailable only if nothing could be fetched at all (#16)
        if qfd_error is not None and council_ok == 0 and areas_ok == 0:
            raise ProviderUnavailableError(qfd_error)
        return hazards

    def _parse_warning_area(self, feature: dict[str, Any], layer: _WarningAreaLayer) -> CanonicalHazard | None:
        """Map a warning-area polygon from the QFD or QPS ArcGIS layer (#30)."""
        props = as_dict(feature.get("properties"))
        unique_id = str(props.get("UniqueID") or "").strip()
        area = simplify_area(rings_from_geojson(feature.get("geometry")))
        if not unique_id or area is None:
            return None
        lat, lon = area_point(area, as_float(self.config.get("latitude")), as_float(self.config.get("longitude")))
        title = str(props.get("WarningTitle") or "").strip() or f"{layer.agency} warning"
        level = WarningLevel.from_str(str(props.get("WarningLevel") or ""))
        if level is WarningLevel.UNKNOWN:
            level = WarningLevel.from_str(title)
        hazard_type = HazardType.from_str(title)
        return CanonicalHazard(
            id=f"{layer.id_prefix}_{unique_id}",
            source=layer.agency,
            title=title,
            hazard_type=layer.default_type if hazard_type is HazardType.OTHER else hazard_type,
            warning_level=level,
            latitude=lat,
            longitude=lon,
            updated_at=self.parse_datetime(props.get("ModifiedDate") or props.get("last_edited_date")),
            location_name=str(props.get("WarningArea") or "").strip() or "Queensland",
            status="Active",
            responsible_agency=layer.agency,
            web_url=layer.web_url,
            area=area,
            call_to_action=str(props.get("CallToAction") or "").strip() or None,
            attribution=DATA_SOURCES[layer.source_key].attribution,
            raw_properties={"unique_id": unique_id, "incident_number": props.get("MasterIncidentNum")},
        )

    @staticmethod
    def _add_parsed(
        hazards: list[CanonicalHazard],
        seen_ids: set[str],
        parse: Any,
        item: Any,
        label: str,
    ) -> None:
        """Parse one upstream item into ``hazards``; a malformed item is skipped, not fatal."""
        try:
            hazard = parse(item)
        except MALFORMED_ITEM_ERRORS as err:
            _LOGGER.debug("Skipping malformed %s item: %s", label, err)
            return
        if hazard and hazard.id not in seen_ids:
            seen_ids.add(hazard.id)
            hazards.append(hazard)

    async def _fetch_council_hazards(
        self, dashboard: GuardianDashboard, seen_ids: set[str]
    ) -> tuple[list[CanonicalHazard], int]:
        """Fetch located hazards from the council dashboard; return (hazards, endpoints fetched OK).

        Only items with their own location become hazards: QLDTraffic road events and
        council bulletins with geometry. The dashboard's BoM summary has no location and is
        exposed as weather warnings instead (#25). ``fireDetailed`` is not used: it is a
        statewide list without coordinates (#12).
        """
        hazards: list[CanonicalHazard] = []
        fetched_ok = 0

        road_data = await dashboard.fetch("tmrRoadData")
        if isinstance(road_data, list):
            fetched_ok += 1
            for item in road_data:
                self._add_parsed(hazards, seen_ids, self._parse_council_road_item, item, "council road")

        bulletin_data = await dashboard.fetch("imsBulletin")
        if isinstance(bulletin_data, dict) and isinstance(bulletin_data.get("features"), list):
            fetched_ok += 1
            for feat in bulletin_data["features"]:
                self._add_parsed(hazards, seen_ids, self._parse_council_bulletin_feature, feat, "council bulletin")

        return hazards, fetched_ok

    def _parse_qfd_feature(self, feature: dict[str, Any]) -> CanonicalHazard | None:
        """Parse a feature from QFD bushfireAlert.json (fields verified against the live feed, #12)."""
        properties = feature.get("properties") or {}
        raw_uid = properties.get("UniqueID") or properties.get("OBJECTID") or properties.get("Incident_Number")
        if not raw_uid or not (unique_id := str(raw_uid).strip()):
            return None

        point = _valid_point(properties.get("Latitude"), properties.get("Longitude")) or self.calculate_centroid(
            feature.get("geometry") or {}
        )
        if not point:
            return None
        lat, lon = point

        locality = str(properties.get("WarningArea") or properties.get("Locality") or "").strip()
        # Titles such as "Information - " omit the area when QFD has none
        title = _TRAILING_DASH_RE.sub("", str(properties.get("WarningTitle") or properties.get("Incident_Name") or ""))
        if not title:
            title = "Queensland Fire Incident"
        if title.lower() in ("information", "advice", "watch and act", "emergency warning") and locality:
            title = f"{title} - {locality}"

        raw_level = properties.get("WarningLevel") or properties.get("Alert_Level")
        warning_level = WarningLevel.from_str(str(raw_level))

        grouped_type = str(properties.get("GroupedType") or "")
        raw_type = grouped_type or properties.get("EventType") or properties.get("Incident_Type") or "Bushfire"
        hazard_type = HazardType.from_str(str(raw_type))

        updated_at = self.parse_datetime(
            properties.get("ItemDateTimeLocal_ISO") or properties.get("LastUpdate") or properties.get("Updated")
        )

        road = str(properties.get("Location") or "").strip()
        location_name = ", ".join(part for part in (road, locality) if part) or "Queensland"

        markers = f"{title} {grouped_type}".lower()
        is_hazard_reduction = bool(
            "hazard reduction" in markers
            or "planned burn" in markers
            or "permitted burn" in markers
            or properties.get("Is_Hazard_Reduction")
        )

        return CanonicalHazard(
            id=f"QLD_QFD_{unique_id}",
            source="Queensland Fire Department",
            title=title,
            hazard_type=hazard_type,
            warning_level=warning_level,
            latitude=lat,
            longitude=lon,
            updated_at=updated_at,
            location_name=location_name,
            is_hazard_reduction=is_hazard_reduction,
            status=properties.get("CurrentStatus") or properties.get("Status"),
            responsible_agency="Queensland Fire Department",
            web_url=QFD_WEB_URL,
            raw_properties=properties,
        )

    def _parse_council_road_item(self, item: dict[str, Any]) -> CanonicalHazard | None:
        """Parse a QLDTraffic road event from Guardian IMS /dashboard/tmrRoadData."""
        props = item.get("properties") or {}
        centroid = self.calculate_centroid(item.get("geometry") or {})
        if not centroid:
            return None
        lat, lon = centroid

        raw_road_id = props.get("id") or item.get("id")
        if not raw_road_id:
            return None
        if props.get("status") == "Reopened":
            return None

        event_type = str(props.get("event_type") or "Hazard")
        subtype = str(props.get("event_subtype") or "")
        impact = as_dict(props.get("impact"))
        impact_subtype = str(impact.get("impact_subtype") or "")
        summary = as_dict(props.get("road_summary"))
        road_name = str(summary.get("road_name") or props.get("road") or "")

        title = f"{event_type}: {subtype}" if subtype else event_type
        if road_name:
            title = f"{title} - {road_name}"

        duration = as_dict(props.get("duration"))
        updated_at = self.parse_datetime(props.get("last_updated") or props.get("published") or duration.get("start"))

        # Road events are information, or advice when lanes or the road are closed
        closed = "closed" in impact_subtype.lower() or "closed" in subtype.lower()
        warning_level = WarningLevel.ADVICE if closed else WarningLevel.INFORMATION

        source_info = as_dict(props.get("source"))
        locality = summary.get("locality") or props.get("suburb")

        return CanonicalHazard(
            id=f"QLD_COUNCIL_ROAD_{raw_road_id}",
            source="QLDTraffic / Council",
            title=title,
            hazard_type=HazardType.ROAD_INCIDENT,
            warning_level=warning_level,
            latitude=lat,
            longitude=lon,
            updated_at=updated_at,
            location_name=str(locality or road_name or "Queensland"),
            status=impact_subtype or props.get("status"),
            responsible_agency=source_info.get("provided_by") or "QLDTraffic / Council",
            web_url=props.get("web_link") or QLDTRAFFIC_WEB_URL,
            raw_properties=props,
        )

    def _parse_council_bulletin_feature(self, feature: dict[str, Any]) -> CanonicalHazard | None:
        """Parse a council bulletin with geometry from /dashboard/imsBulletin.

        A bulletin without geometry has no location and is only listed as news; it is
        never placed at a default point.
        """
        props = feature.get("properties") or {}
        centroid = self.calculate_centroid(feature.get("geometry") or {})
        raw_id = props.get("id") or props.get("bulletin_id")
        if not centroid or not raw_id:
            return None

        title = str(props.get("title") or props.get("headline") or "Council Disaster Bulletin").strip()
        warning_level = WarningLevel.from_str(props.get("priority") or props.get("level"))
        if warning_level == WarningLevel.UNKNOWN:
            warning_level = WarningLevel.ADVICE

        return CanonicalHazard(
            id=f"QLD_COUNCIL_BULLETIN_{raw_id}",
            source="Council Disaster Operations",
            title=title,
            hazard_type=HazardType.OTHER,
            warning_level=warning_level,
            latitude=centroid[0],
            longitude=centroid[1],
            updated_at=self.parse_datetime(props.get("created") or props.get("updated")),
            location_name=str(props.get("suburb") or ""),
            status="Active",
            responsible_agency="Local Disaster Management Group",
            web_url=props.get("url"),
            raw_properties=props,
        )

    async def async_fetch_power_outages(self) -> list[PowerOutageItem]:
        """Fetch Ergon and Energex power outages from the council dashboard."""
        return await self.dashboard.power_outages() if self.dashboard else []

    async def async_fetch_road_closures(self) -> list[RoadClosureItem]:
        """Fetch council road closures and QLDTraffic events."""
        return await self.dashboard.road_closures() if self.dashboard else []

    async def async_fetch_weather_warnings(self) -> list[WeatherWarningItem]:
        """Fetch the BoM warning summary from the council dashboard."""
        return await self.dashboard.weather_warnings() if self.dashboard else []

    async def async_fetch_emergency_news(self) -> list[EmergencyNewsItem]:
        """Fetch council emergency bulletins."""
        return await self.dashboard.emergency_news() if self.dashboard else []

    async def async_fetch_fire_danger(self) -> FireDangerRating | None:
        """Fetch the AFDRS fire danger rating from the council dashboard."""
        return await self.dashboard.fire_danger() if self.dashboard else None

    async def async_fetch_weather_telemetry(self) -> list[WeatherStationObservation]:
        """Fetch weather observations for the council's stations."""
        return await self.dashboard.weather_telemetry() if self.dashboard else []

    async def async_fetch_air_quality(self) -> list[AirQualityStationData]:
        """Fetch air quality for the council's monitoring stations."""
        return await self.dashboard.air_quality() if self.dashboard else []

    async def async_fetch_relief_facilities(self) -> list[ReliefFacilityItem]:
        """Fetch evacuation centres, places of refuge and sandbag points."""
        return await self.dashboard.relief_facilities() if self.dashboard else []

    async def async_fetch_cameras(self) -> list[DisasterCameraItem]:
        """Fetch the council dashboard's flood and traffic cameras."""
        return await self.dashboard.cameras() if self.dashboard else []

    async def async_fetch_nearby_councils(self) -> list[dict[str, str]]:
        """Return links to the QLD council dashboards nearest the monitored point (#32).

        The links come from the generated council registry and are never polled.
        """
        if not self.dashboard:
            return []
        return nearby_council_links(
            "QLD",
            self.config.get("latitude"),
            self.config.get("longitude"),
            self.dashboard.base_url if self.dashboard else None,
        )
