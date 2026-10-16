"""Western Australia Emergency Hazard Provider (Emergency WA / DFES).

Warnings and incidents come from Emergency WA's designated RSS feeds (#61): its terms exempt
only the RSS, CAP-AU and SLIP feeds from the no-copying clause. The warnings feed carries the
warning area as a ``georss:polygon`` of ``lat,lon`` pairs (#30). Fire danger ratings still come
from ``/v1/fire-danger-ratings``, which has no designated alternative (see the data source
register).

The feeds declare non-standard namespace URIs (``https://www.ogc.org/standard/georss/``,
``https://www.w3.org/2003/01/geo/wgs84_pos#``), so item children are matched by local name.
"""

from __future__ import annotations

import html
import logging
import re
from typing import TYPE_CHECKING, Any

import aiohttp
import defusedxml.ElementTree as ET

from custom_components.ausnz_disaster_watch.const import STATE_WA
from custom_components.ausnz_disaster_watch.fire_districts import FIRE_DISTRICTS, resolve_district
from custom_components.ausnz_disaster_watch.models import CanonicalHazard, FireDangerRating, HazardType, WarningLevel

from .base import MALFORMED_ITEM_ERRORS, BaseHazardProvider, ProviderUnavailableError, stable_id
from .geometry import ring_from_latlon_text, simplify_area

if TYPE_CHECKING:
    from xml.etree.ElementTree import Element

_LOGGER = logging.getLogger(__name__)

WA_INCIDENTS_URL = "https://api.emergency.wa.gov.au/v1/rss/incidents"
WA_WARNINGS_URL = "https://api.emergency.wa.gov.au/v1/rss/warnings"
# Not a designated feed; kept because nothing else publishes district ratings (register, #61)
WA_FDR_URL = "https://api.emergency.wa.gov.au/v1/fire-danger-ratings"
WA_WEB_URL = "https://www.emergency.wa.gov.au"

# "Bushfire (BRIDGETOWN, SHIRE OF BRIDGETOWN-GREENBUSHES, LOWER SOUTH WEST, CAD-ID: 820504)"
_INCIDENT_TITLE_RE = re.compile(r"^(?P<type>.+?)\s*\((?P<where>.*)\)\s*$")
_CAD_ID_RE = re.compile(r",?\s*CAD-ID:\s*([\w-]+)", re.IGNORECASE)
_WARNING_TYPE_RE = re.compile(r'data-warning-type="([^"]+)"')
# Private and agency burn-offs are planned burns (hazard reduction, #14)
_HAZARD_REDUCTION_TYPES = ("burn off", "prescribed burn", "planned burn", "hazard reduction")


def _child_text(item: Element, name: str) -> str:
    """Return the text of the first child with local name ``name``, whatever its namespace."""
    for child in item:
        if child.tag.rsplit("}", 1)[-1] == name:
            return (child.text or "").strip()
    return ""


def _point(item: Element) -> tuple[float, float] | None:
    """Return (lat, lon) from ``geo:lat``/``geo:long``, or None if absent or invalid."""
    try:
        lat, lon = float(_child_text(item, "lat")), float(_child_text(item, "long"))
    except ValueError:
        return None
    if -90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0 and (lat, lon) != (0.0, 0.0):
        return lat, lon
    return None


class WAHazardProvider(BaseHazardProvider):
    """Provider for Western Australia DFES / Emergency WA incident and warning feeds."""

    local_tz = "Australia/Perth"

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialise the provider with a per-instance fire danger district cache."""
        super().__init__(*args, **kwargs)
        # ((lat, lon), district AAC) for the last resolved fire danger location
        self._fdr_area: tuple[tuple[float, float], str | None] | None = None

    @property
    def state_code(self) -> str:
        """Return jurisdiction identifier."""
        return STATE_WA

    async def async_fetch_hazards(self) -> list[CanonicalHazard]:
        """Fetch active warnings and incidents from the Emergency WA RSS feeds."""
        return await self.async_collect_sources(
            [
                (
                    "Emergency WA warnings",
                    lambda: self.async_fetch_feed_text(WA_WARNINGS_URL, "Emergency WA warnings"),
                    self._parse_warnings,
                ),
                (
                    "Emergency WA incidents",
                    lambda: self.async_fetch_feed_text(WA_INCIDENTS_URL, "Emergency WA incidents"),
                    self._parse_incidents,
                ),
            ]
        )

    async def async_fetch_fire_danger(self) -> FireDangerRating | None:
        """Fetch today's Fire Danger Rating for the configured location's fire weather district.

        The feed lists every WA district (``area`` is the BoM AAC, ``description`` the name)
        with forecasts keyed by day offset. It has no total fire ban field (#14). It is not one
        of Emergency WA's designated feeds; the data source register records it as restricted.
        """
        try:
            lat = float(self.config["latitude"])
            lon = float(self.config["longitude"])
        except (KeyError, TypeError, ValueError):
            return None

        # The polygon test reads a file and scans thousands of edges, so it runs in an
        # executor, once per location
        if self._fdr_area is None or self._fdr_area[0] != (lat, lon):
            area = await self.hass.async_add_executor_job(resolve_district, FIRE_DISTRICTS, lat, lon, "WA_")
            self._fdr_area = ((lat, lon), area)
        area = self._fdr_area[1]
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

    def _items(self, xml_text: str, label: str) -> list[Element]:
        """Return the RSS items; a blank body, invalid XML or a non-RSS document is a broken feed (#16)."""
        if not xml_text.strip():
            raise ProviderUnavailableError(f"{label} returned an empty response")
        try:
            root = ET.fromstring(xml_text)
        except (ET.ParseError, ValueError) as err:
            raise ProviderUnavailableError(f"{label} returned invalid XML: {err}") from err
        self.require_xml_root(root, "rss", label)
        return root.findall("./channel/item")

    def _parse_warnings(self, xml_text: str) -> list[CanonicalHazard]:
        """Parse the Emergency WA warnings RSS feed (closures on the same feed are skipped)."""
        hazards: list[CanonicalHazard] = []
        for item in self._items(xml_text, "Emergency WA warnings"):
            try:
                hazard = self._parse_warning(item)
            except MALFORMED_ITEM_ERRORS as err:
                _LOGGER.debug("Skipping malformed Emergency WA warning item: %s", err)
                continue
            if hazard is not None:
                hazards.append(hazard)
        return hazards

    def _parse_warning(self, item: Element) -> CanonicalHazard | None:
        """Map one warning item; its ``georss:polygon`` becomes the hazard area (#30)."""
        link = _child_text(item, "link")
        if "/closures/" in link:
            # Facility and park closures share the feed but are not hazards
            return None
        title = _child_text(item, "title") or "Emergency WA Warning"
        region = _child_text(item, "region")
        ring = ring_from_latlon_text(_child_text(item, "polygon"))
        area = simplify_area([ring]) if ring else None
        point = _point(item) or (area[0][0] if area else None)
        if point is None:
            # Never invent a location: an unlocated warning would be counted as nearby
            return None

        # The warning type ("Bushfire Watch and Act", "Smoke Alert") names the AWS level; the
        # title alone can mislead (a place called "Emergency Beach")
        type_match = _WARNING_TYPE_RE.search(_child_text(item, "description"))
        warning_type = html.unescape(type_match.group(1)) if type_match else ""
        level = WarningLevel.from_str(_child_text(item, "alertLevel"))
        if level is WarningLevel.UNKNOWN:
            level = WarningLevel.from_str(warning_type or title)

        place = title.rsplit(" - ", 1)[1].strip() if " - " in title else ""
        # Fallback uses fields that do not change when the warning is updated (#7)
        item_id = _child_text(item, "guid") or stable_id("wa_warn", title, place or region, *point)
        return CanonicalHazard(
            id=f"wa_warn_{item_id}",
            source="Emergency WA / DFES",
            title=title,
            hazard_type=HazardType.from_str(warning_type or title),
            warning_level=level,
            latitude=point[0],
            longitude=point[1],
            updated_at=self.parse_datetime(_child_text(item, "publicationTime") or _child_text(item, "pubDate")),
            location_name=(place or region or "WA").title(),
            status="Active",
            responsible_agency="DFES Western Australia",
            web_url=link or WA_WEB_URL,
            area=area,
            raw_properties={
                "warning_type": warning_type or None,
                "region": region or None,
                "incident_number": _child_text(item, "incidentNumber") or None,
            },
        )

    def _parse_incidents(self, xml_text: str) -> list[CanonicalHazard]:
        """Parse the Emergency WA incidents RSS feed."""
        hazards: list[CanonicalHazard] = []
        for item in self._items(xml_text, "Emergency WA incidents"):
            try:
                hazard = self._parse_incident(item)
            except MALFORMED_ITEM_ERRORS as err:
                _LOGGER.debug("Skipping malformed Emergency WA incident item: %s", err)
                continue
            if hazard is not None:
                hazards.append(hazard)
        return hazards

    def _parse_incident(self, item: Element) -> CanonicalHazard | None:
        """Map one incident item; its title is "Type (LOCALITY, LGA, REGION, CAD-ID: n)"."""
        point = _point(item)
        if point is None:
            return None
        raw_title = _child_text(item, "title")
        match = _INCIDENT_TITLE_RE.match(raw_title)
        inc_type = match.group("type").strip() if match else (raw_title or "Incident")
        where = _CAD_ID_RE.sub("", match.group("where")) if match else ""
        parts = [part.strip().title() for part in where.split(",") if part.strip()]
        locality = parts[0] if parts else "WA"
        cad = _CAD_ID_RE.search(raw_title)
        item_id = _child_text(item, "guid") or stable_id("wa_inc", inc_type, raw_title, *point)
        return CanonicalHazard(
            id=f"wa_inc_{item_id}",
            source="Emergency WA / DFES",
            title=f"{inc_type} - {locality}",
            hazard_type=HazardType.from_str(inc_type),
            warning_level=WarningLevel.INFORMATION,
            latitude=point[0],
            longitude=point[1],
            updated_at=self.parse_datetime(_child_text(item, "pubDate")),
            location_name=", ".join(parts) or "WA",
            is_hazard_reduction=any(kind in inc_type.lower() for kind in _HAZARD_REDUCTION_TYPES),
            responsible_agency="DFES Western Australia",
            web_url=_child_text(item, "link") or WA_WEB_URL,
            raw_properties={"cad_id": cad.group(1) if cad else None, "region": parts[-1] if len(parts) > 1 else None},
        )
