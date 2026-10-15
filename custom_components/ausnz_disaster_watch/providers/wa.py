"""Western Australia Emergency Hazard Provider (Emergency WA / DFES)."""

from __future__ import annotations

import logging
from typing import Any, ClassVar

import aiohttp

from custom_components.ausnz_disaster_watch.const import STATE_WA
from custom_components.ausnz_disaster_watch.fire_districts import find_district, load_fire_districts
from custom_components.ausnz_disaster_watch.models import CanonicalHazard, FireDangerRating, HazardType, WarningLevel

from .base import MALFORMED_ITEM_ERRORS, BaseHazardProvider, stable_id

_LOGGER = logging.getLogger(__name__)

WA_INCIDENTS_URL = "https://api.emergency.wa.gov.au/v1/incidents"
WA_WARNINGS_URL = "https://api.emergency.wa.gov.au/v1/warnings"
WA_FDR_URL = "https://api.emergency.wa.gov.au/v1/fire-danger-ratings"
WA_FIRE_DISTRICTS = "wa_fire_districts"


class WAHazardProvider(BaseHazardProvider):
    """Provider for Western Australia DFES / Emergency WA incident and warning feeds."""

    local_tz = "Australia/Perth"

    # BoM fire weather district polygons, loaded once off the event loop
    _districts: ClassVar[dict[str, dict[str, Any]] | None] = None

    @property
    def state_code(self) -> str:
        """Return jurisdiction identifier."""
        return STATE_WA

    async def async_fetch_hazards(self) -> list[CanonicalHazard]:
        """Fetch active warnings and CAD incidents from Emergency WA API."""
        return await self.async_collect_sources(
            [
                (
                    "Emergency WA warnings",
                    lambda: self.async_fetch_feed_json(WA_WARNINGS_URL, "Emergency WA warnings"),
                    lambda payload: self._parse_warnings(self.require_dict(payload, "Emergency WA warnings")),
                ),
                (
                    "Emergency WA incidents",
                    lambda: self.async_fetch_feed_json(WA_INCIDENTS_URL, "Emergency WA incidents"),
                    lambda payload: self._parse_incidents(self.require_dict(payload, "Emergency WA incidents")),
                ),
            ]
        )

    async def async_fetch_fire_danger(self) -> FireDangerRating | None:
        """Fetch today's Fire Danger Rating for the configured location's fire weather district.

        The feed lists every WA district (``area`` is the BoM AAC, ``description`` the name)
        with forecasts keyed by day offset. It has no total fire ban field (#14).
        """
        try:
            lat = float(self.config["latitude"])
            lon = float(self.config["longitude"])
        except (KeyError, TypeError, ValueError):
            return None

        districts = WAHazardProvider._districts
        if districts is None:
            districts = await self.hass.async_add_executor_job(load_fire_districts, WA_FIRE_DISTRICTS)
            WAHazardProvider._districts = districts
        area = find_district(districts, lat, lon)
        if area is None:
            # Outside every WA district: report unknown rather than another district's rating
            return None

        try:
            data = await self.async_fetch_json(WA_FDR_URL)
        except (aiohttp.ClientError, TimeoutError, ValueError) as err:
            _LOGGER.debug("Failed to fetch WA fire danger rating: %s", err)
            return None

        ratings = data.get("fireDangerRatings") if isinstance(data, dict) else None
        for item in ratings if isinstance(ratings, list) else []:
            if not isinstance(item, dict) or item.get("area") != area:
                continue
            forecasts = item.get("forecasts")
            today = forecasts.get("0") if isinstance(forecasts, dict) else None
            rating = today.get("fireDanger") if isinstance(today, dict) else None
            if not rating:
                return None
            return FireDangerRating(
                district_number=area,
                district_name=str(item.get("description") or area),
                rating=str(rating),
                total_fire_ban=None,
                day="Today",
            )
        return None

    def _parse_warnings(self, payload: dict[str, Any]) -> list[CanonicalHazard]:
        """Parse Emergency WA warnings."""
        hazards: list[CanonicalHazard] = []
        warnings = self.require_list(payload, "warnings", "Emergency WA warnings")

        for item in warnings:
            try:
                title = str(item.get("title") or item.get("name") or "Emergency Warning")
                loc = item.get("location") or {}
                # Fallback uses fields that do not change when the warning is updated (#7)
                item_id = str(
                    item.get("id")
                    or stable_id("wa_warn", title, loc.get("value"), loc.get("latitude"), loc.get("longitude"))
                )
                sub_type = str(item.get("entitySubType", "")).lower()
                warn_type = str(item.get("warning-type", "")).lower()

                if "emergency" in sub_type or "emergency" in warn_type:
                    level = WarningLevel.EMERGENCY_WARNING
                elif "watch" in sub_type or "watch" in warn_type:
                    level = WarningLevel.WATCH_AND_ACT
                elif "advice" in sub_type or "advice" in warn_type:
                    level = WarningLevel.ADVICE
                else:
                    level = WarningLevel.from_str(warn_type)

                loc_data = item.get("location", {})
                lat = loc_data.get("latitude")
                lon = loc_data.get("longitude")

                if lat is None or lon is None:
                    # Try centroid from geo-source
                    geo_source = item.get("geo-source", {})
                    centroid = self.calculate_centroid(geo_source)
                    if centroid:
                        lat, lon = centroid

                if lat is None or lon is None:
                    continue

                event_type = item.get("cap-category") or item.get("incident-type") or title
                suburbs = item.get("suburbs", [])
                locality = ", ".join(suburbs) if suburbs else str(loc_data.get("value", "WA"))

                hazards.append(
                    CanonicalHazard(
                        id=f"wa_warn_{item_id}",
                        source="Emergency WA / DFES",
                        title=title,
                        hazard_type=HazardType.from_str(str(event_type)),
                        warning_level=level,
                        latitude=float(lat),
                        longitude=float(lon),
                        updated_at=self.parse_datetime(item.get("updatedAt") or item.get("issued-date-time")),
                        location_name=locality,
                        status=str(item.get("action-statement", "Active")),
                        responsible_agency="DFES Western Australia",
                        web_url=f"https://www.emergency.wa.gov.au/#/warning/{item_id}",
                        raw_properties={
                            "urgency": item.get("cap-urgency"),
                            "severity": item.get("cap-severity"),
                            "headline": item.get("headline"),
                        },
                    )
                )
            except MALFORMED_ITEM_ERRORS as err:
                _LOGGER.debug("Skipping malformed Emergency WA warning item: %s", err)

        return hazards

    def _parse_incidents(self, payload: dict[str, Any]) -> list[CanonicalHazard]:
        """Parse Emergency WA active incidents."""
        hazards: list[CanonicalHazard] = []
        incidents = self.require_list(payload, "incidents", "Emergency WA incidents")

        for item in incidents:
            try:
                inc_type = str(item.get("incident-type", "Incident"))
                inc_loc = item.get("location") or {}
                item_id = str(
                    item.get("id")
                    or stable_id(
                        "wa_inc",
                        inc_type,
                        item.get("name"),
                        inc_loc.get("value"),
                        inc_loc.get("latitude"),
                        inc_loc.get("longitude"),
                    )
                )
                status = str(item.get("incident-status", "Monitoring"))
                loc_data = item.get("location", {})
                lat = loc_data.get("latitude")
                lon = loc_data.get("longitude")

                if lat is None or lon is None:
                    geo_source = item.get("geo-source", {})
                    centroid = self.calculate_centroid(geo_source)
                    if centroid:
                        lat, lon = centroid

                if lat is None or lon is None:
                    continue

                suburbs = item.get("suburbs", [])
                locality = ", ".join(suburbs) if suburbs else str(loc_data.get("value", "WA"))
                title = f"{inc_type} - {locality}"

                hazards.append(
                    CanonicalHazard(
                        id=f"wa_inc_{item_id}",
                        source="Emergency WA / DFES",
                        title=title,
                        hazard_type=HazardType.from_str(inc_type),
                        warning_level=WarningLevel.INFORMATION,
                        latitude=float(lat),
                        longitude=float(lon),
                        updated_at=self.parse_datetime(item.get("updatedAt") or item.get("issued-date-time")),
                        location_name=locality,
                        status=status,
                        responsible_agency="DFES Western Australia",
                        web_url="https://www.emergency.wa.gov.au",
                        raw_properties={
                            "cad_id": item.get("cad-id"),
                            "dfes_regions": item.get("dfes-regions"),
                        },
                    )
                )
            except MALFORMED_ITEM_ERRORS as err:
                _LOGGER.debug("Skipping malformed Emergency WA incident item: %s", err)

        return hazards
