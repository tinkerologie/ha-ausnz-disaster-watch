"""New South Wales emergency hazards provider (NSW RFS & SES)."""

from __future__ import annotations

import logging
import re
from typing import Any

from custom_components.ausnz_disaster_watch.const import CONF_COUNCIL_DASHBOARD_URL, STATE_NSW
from custom_components.ausnz_disaster_watch.models import (
    CanonicalHazard,
    EmergencyNewsItem,
    FireDangerRating,
    HazardType,
    WarningLevel,
    WeatherWarningItem,
)

from .base import MALFORMED_ITEM_ERRORS, BaseHazardProvider, ProviderUnavailableError

_LOGGER = logging.getLogger(__name__)

NSW_RFS_MAJOR_INCIDENTS_URL = "https://www.rfs.nsw.gov.au/feeds/majorIncidents.json"
DEFAULT_NSW_COUNCIL_URL = "https://disaster.hawkesbury.nsw.gov.au"


class NSWHazardProvider(BaseHazardProvider):
    """Provider for New South Wales Rural Fire Service and State Emergency Service."""

    local_tz = "Australia/Sydney"

    @property
    def state_code(self) -> str:
        """Return state code."""
        return STATE_NSW

    async def async_fetch_hazards(self) -> list[CanonicalHazard]:
        """Fetch hazards from NSW RFS major incidents feed."""
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

    def _get_council_base_url(self) -> str | None:
        """Return configured NSW Council Disaster Dashboard base URL or None."""
        url = self.config.get(CONF_COUNCIL_DASHBOARD_URL)
        if not url:
            return None
        return str(url).strip().rstrip("/")

    async def async_fetch_fire_danger(self) -> FireDangerRating | None:
        """Fetch AFDRS fire danger rating from NSW Council dashboard."""
        base_url = self._get_council_base_url()
        if not base_url:
            return None
        try:
            fdr_data = await self.async_fetch_json(f"{base_url}/dashboard/fireDangerRating")
            if isinstance(fdr_data, dict):
                data_list = fdr_data.get("Data", [])
                if isinstance(data_list, list) and len(data_list) > 0:
                    first = data_list[0]
                    toban = str(first.get("TOBAN", "")).lower() in ("yes", "true", "1")
                    return FireDangerRating(
                        district_number=str(first.get("District_Number", "")),
                        district_name=str(first.get("District_Name", "")),
                        rating=str(first.get("FDR", "Moderate")),
                        total_fire_ban=toban,
                        day=first.get("Day"),
                    )
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("Error fetching NSW Fire Danger Rating: %s", err)
        return None

    async def async_fetch_weather_warnings(self) -> list[WeatherWarningItem]:
        """Fetch weather warnings summary from NSW council BoM feed."""
        base_url = self._get_council_base_url()
        if not base_url:
            return []
        warnings: list[WeatherWarningItem] = []
        try:
            bom_data = await self.async_fetch_json(f"{base_url}/dashboard/bom")
            if isinstance(bom_data, dict):
                items = bom_data.get("item", [])
                if isinstance(items, list):
                    for item in items:
                        title = str(item.get("title", "")).strip()
                        if not title:
                            continue
                        warnings.append(
                            WeatherWarningItem(
                                title=title,
                                link=item.get("link"),
                                locations=item.get("locations"),
                                pub_date=self.parse_datetime(item.get("pubDate")),
                            )
                        )
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("Error fetching NSW weather warnings: %s", err)
        return warnings

    async def async_fetch_emergency_news(self) -> list[EmergencyNewsItem]:
        """Fetch emergency bulletins from NSW Council dashboard."""
        base_url = self._get_council_base_url()
        if not base_url:
            return []
        news_list: list[EmergencyNewsItem] = []
        try:
            bulletin_data = await self.async_fetch_json(f"{base_url}/dashboard/imsBulletin")
            if isinstance(bulletin_data, dict):
                features = bulletin_data.get("features", [])
                for feat in features:
                    props = feat.get("properties", {})
                    raw_id = str(props.get("id") or props.get("bulletin_id") or len(news_list))
                    title = str(props.get("title") or props.get("headline") or "Disaster News").strip()
                    news_list.append(
                        EmergencyNewsItem(
                            id=raw_id,
                            title=title,
                            description=props.get("description") or props.get("content"),
                            link=props.get("url"),
                            pub_date=self.parse_datetime(props.get("created") or props.get("updated")),
                        )
                    )
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("Error fetching NSW emergency news bulletins: %s", err)
        return news_list

    async def async_fetch_nearby_councils(self) -> list[dict[str, str]]:
        """Fetch nearby NSW council disaster dashboard links."""
        return [
            {"name": "Hawkesbury City Council", "url": "https://disaster.hawkesbury.nsw.gov.au"},
            {"name": "Blue Mountains City Council", "url": "https://emergency.bmcc.nsw.gov.au"},
            {"name": "Tweed Shire Council", "url": "https://emergency.tweed.nsw.gov.au"},
            {"name": "Ballina Shire Council", "url": "https://emergency.ballina.nsw.gov.au"},
            {"name": "Bega Valley Shire Council", "url": "https://disaster.begavalley.nsw.gov.au"},
        ]
