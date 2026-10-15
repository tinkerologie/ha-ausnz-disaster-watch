"""New South Wales emergency hazards provider (NSW RFS & SES)."""

from __future__ import annotations

import logging
import re
from typing import Any

from custom_components.ausnz_disaster_watch.const import CONF_COUNCIL_DASHBOARD_URL, STATE_NSW
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

from .base import MALFORMED_ITEM_ERRORS, BaseHazardProvider, ProviderUnavailableError
from .guardian_ims import GuardianDashboard, normalise_dashboard_url

_LOGGER = logging.getLogger(__name__)

NSW_RFS_MAJOR_INCIDENTS_URL = "https://www.rfs.nsw.gov.au/feeds/majorIncidents.json"

# Links to NSW council dashboards (shown on the card; never polled)
NSW_COUNCIL_LINKS: list[dict[str, str]] = [
    {"name": "Hawkesbury City Council", "url": "https://disaster.hawkesbury.nsw.gov.au"},
    {"name": "Blue Mountains City Council", "url": "https://emergency.bmcc.nsw.gov.au"},
    {"name": "Ballina Shire Council", "url": "https://emergency.ballina.nsw.gov.au"},
    {"name": "Byron Shire Council", "url": "https://emergency.byron.nsw.gov.au"},
    {"name": "Northern Beaches Council", "url": "https://emergency.northernbeaches.nsw.gov.au"},
]


class NSWHazardProvider(BaseHazardProvider):
    """Provider for New South Wales Rural Fire Service and State Emergency Service."""

    local_tz = "Australia/Sydney"

    @property
    def state_code(self) -> str:
        """Return state code."""
        return STATE_NSW

    async def async_fetch_hazards(self) -> list[CanonicalHazard]:
        """Fetch hazards from NSW RFS major incidents feed."""
        if self.dashboard is not None:
            self.dashboard.start_poll()
        data = await self.async_fetch_feed_json(NSW_RFS_MAJOR_INCIDENTS_URL, "NSW RFS")
        if not isinstance(data, dict):
            raise ProviderUnavailableError("NSW RFS returned an unexpected payload")

        hazards: list[CanonicalHazard] = []
        for feature in self.require_list(data, "features", "NSW RFS"):
            try:
                hazard = self._parse_nsw_feature(feature)
            except MALFORMED_ITEM_ERRORS as err:
                _LOGGER.debug("Skipping malformed NSW RFS item: %s", err)
                continue
            if hazard:
                hazards.append(hazard)
        return hazards

    def _parse_nsw_feature(self, feature: dict[str, Any]) -> CanonicalHazard | None:
        """Parse GeoJSON feature from NSW RFS feed."""
        props = feature.get("properties", {})
        geometry = feature.get("geometry", {})
        centroid = self.calculate_centroid(geometry)
        if not centroid:
            return None

        lat, lon = centroid
        guid = str(props.get("guid", ""))
        inc_id_match = re.search(r"/(\d+)$", guid)
        inc_id = inc_id_match.group(1) if inc_id_match else re.sub(r"\W+", "_", guid)
        if not inc_id:
            title_slug = re.sub(r"\W+", "_", str(props.get("title", "nsw_incident")))
            inc_id = f"{title_slug}_{lat:.4f}_{lon:.4f}"

        title = str(props.get("title", "NSW Incident")).strip()
        category = props.get("category")
        description = str(props.get("description", ""))

        # Parse key-value pairs from HTML description
        desc_fields = self._parse_description_html(description)

        raw_level = desc_fields.get("ALERT LEVEL") or category
        warning_level = WarningLevel.from_str(raw_level)

        raw_type = desc_fields.get("TYPE") or "Bush Fire"
        hazard_type = HazardType.from_str(raw_type)

        location_name = desc_fields.get("LOCATION") or desc_fields.get("COUNCIL AREA") or title

        status = desc_fields.get("STATUS")
        agency = desc_fields.get("RESPONSIBLE AGENCY") or "NSW Rural Fire Service"

        # "UPDATED" in the description is Sydney local time; pubDate is the fallback (#13)
        updated_at = self.parse_datetime(desc_fields.get("UPDATED")) or self.parse_datetime(props.get("pubDate"))

        is_hazard_reduction = bool(
            "hazard reduction" in description.lower()
            or "hazard reduction" in title.lower()
            or "hazard reduction" in raw_type.lower()
        )

        return CanonicalHazard(
            id=f"NSW_RFS_{inc_id}",
            source="NSW Rural Fire Service",
            title=title,
            hazard_type=hazard_type,
            warning_level=warning_level,
            latitude=lat,
            longitude=lon,
            updated_at=updated_at,
            location_name=location_name,
            is_hazard_reduction=is_hazard_reduction,
            status=status,
            responsible_agency=agency,
            web_url=props.get("link") or "https://www.rfs.nsw.gov.au/fire-information/fires-near-me",
            raw_properties=props,
        )

    @staticmethod
    def _parse_description_html(desc: str) -> dict[str, str]:
        """Extract key-value fields from HTML description string."""
        fields: dict[str, str] = {}
        if not desc:
            return fields

        # Splits by <br />, <br/>, or <br>
        lines = re.split(r"<br\s*/?>", desc, flags=re.IGNORECASE)
        for line in lines:
            line = line.strip()
            if ":" in line:
                k, _, v = line.partition(":")
                fields[k.strip().upper()] = v.strip()
        return fields

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialise the provider and its council dashboard client, if one is configured."""
        super().__init__(*args, **kwargs)
        base_url = normalise_dashboard_url(self.config.get(CONF_COUNCIL_DASHBOARD_URL))
        self.dashboard: GuardianDashboard | None = GuardianDashboard(self, base_url) if base_url else None

    async def async_fetch_power_outages(self) -> list[PowerOutageItem]:
        """Fetch power outages published on the council dashboard."""
        return await self.dashboard.power_outages() if self.dashboard else []

    async def async_fetch_road_closures(self) -> list[RoadClosureItem]:
        """Fetch council road closures."""
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
        """Fetch evacuation centres and sandbag points."""
        return await self.dashboard.relief_facilities() if self.dashboard else []

    async def async_fetch_cameras(self) -> list[DisasterCameraItem]:
        """Fetch the council dashboard's cameras."""
        return await self.dashboard.cameras() if self.dashboard else []

    async def async_fetch_nearby_councils(self) -> list[dict[str, str]]:
        """Return links to NSW council disaster dashboards."""
        return [dict(link) for link in NSW_COUNCIL_LINKS]
