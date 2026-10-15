"""Geoscience Australia earthquakes (national, opt-in) (#23).

The GA WFS layer ``earthquakes_seven_days`` (GeoJSON, no key) lists every event GA located
in the last seven days, in Australia and the region. Events of magnitude 3 or more from
the last 48 hours become hazards; the coordinator then keeps those within the configured
radius. Data © Commonwealth of Australia (Geoscience Australia), CC BY 4.0.
"""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from custom_components.ausnz_disaster_watch.models import CanonicalHazard, HazardType, WarningLevel
from homeassistant.util import dt as dt_util

from .base import MALFORMED_ITEM_ERRORS, BaseHazardProvider

_LOGGER = logging.getLogger(__name__)

GA_EARTHQUAKES_URL = (
    "https://earthquakes.ga.gov.au/geoserver/earthquakes/wfs?service=WFS&request=getfeature"
    "&typeNames=earthquakes:earthquakes_seven_days&outputFormat=application/json"
)
GA_EVENT_URL = "https://earthquakes.ga.gov.au/event/{event_id}"
GA_SOURCE = "Geoscience Australia"

GA_MIN_MAGNITUDE = 3.0
# Same cut-off as GeoNet quakes: an old quake should not stay an active hazard for a week
GA_QUAKE_MAX_AGE = timedelta(hours=48)


def quake_level(magnitude: float) -> WarningLevel:
    """Return the warning level for a quake that is within the monitored radius.

    GA publishes no felt intensity, so the level follows magnitude (issue #23): M4.5 or more
    is Watch and Act, M4 or more is Advice, anything smaller is Information.
    """
    if magnitude >= 4.5:
        return WarningLevel.WATCH_AND_ACT
    if magnitude >= 4.0:
        return WarningLevel.ADVICE
    return WarningLevel.INFORMATION


class GAEarthquakeProvider(BaseHazardProvider):
    """Provider for Geoscience Australia earthquakes."""

    local_tz = "UTC"

    @property
    def state_code(self) -> str:
        """Return the national scope."""
        return "AU"

    async def async_fetch_hazards(self) -> list[CanonicalHazard]:
        """Fetch the last seven days of GA earthquakes and keep recent, significant ones."""
        payload = self.require_dict(
            await self.async_fetch_feed_json(GA_EARTHQUAKES_URL, "GA earthquakes"), "GA earthquakes"
        )
        hazards: list[CanonicalHazard] = []
        now = dt_util.utcnow()
        for feature in self.require_list(payload, "features", "GA earthquakes"):
            try:
                hazard = self._parse_feature(feature)
            except MALFORMED_ITEM_ERRORS as err:
                _LOGGER.debug("Skipping malformed GA earthquake: %s", err)
                continue
            # The layer also carries placeholder rows dated 2100; a future time is never current
            if (
                hazard is None
                or hazard.updated_at is None
                or not timedelta(0) <= now - hazard.updated_at <= GA_QUAKE_MAX_AGE
            ):
                continue
            hazards.append(hazard)
        return hazards

    def _parse_feature(self, feature: dict[str, Any]) -> CanonicalHazard | None:
        """Return the hazard for one GA feature, or None for hidden rows and quakes below M3."""
        props: dict[str, Any] = feature["properties"]
        # Rows GA does not display (display_flag "N") are placeholders without an event ID
        if props.get("display_flag") != "Y" or not props.get("event_id"):
            return None
        magnitude = float(props["preferred_magnitude"])
        if magnitude < GA_MIN_MAGNITUDE:
            return None
        event_id = str(props["event_id"])
        description = str(props.get("description") or "Unknown location")
        depth = props.get("depth")
        return CanonicalHazard(
            id=f"ga_quake_{event_id}",
            source=GA_SOURCE,
            title=f"M{magnitude:.1f} Earthquake - {description}",
            hazard_type=HazardType.EARTHQUAKE,
            warning_level=quake_level(magnitude),
            latitude=float(props["latitude"]),
            longitude=float(props["longitude"]),
            # origin_time is when the quake happened (epicentral_time is unreliable in the feed)
            updated_at=self.parse_datetime(props.get("origin_time")),
            location_name=description,
            status=str(props.get("evaluation_status") or "").title() or None,
            responsible_agency=GA_SOURCE,
            web_url=GA_EVENT_URL.format(event_id=event_id),
            raw_properties={
                "magnitude": round(magnitude, 1),
                "magnitude_type": props.get("preferred_magnitude_type"),
                "depth_km": round(float(depth), 1) if depth is not None else None,
                "located_in_australia": props.get("located_in_australia") == "Y",
                "felt_reports": props.get("felt_reports_count"),
                "felt_report_url": props.get("felt_report_url"),
            },
        )
