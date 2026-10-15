"""Northern Territory Emergency Hazard Provider (NT Government Fire_Incidents service).

Reads the NT Government ArcGIS ``Hosted/Fire_Incidents`` FeatureServer, which the NT
Government publishes for its fire incident map. It replaces the PFES ``incidents.json``
file, which states "Please do not use, scrape or re-publish this file" (#34). Layer 0
(Bushfires NT) and layer 1 (NT Fire and Rescue Service) are point layers with the same
fields; layer 2 holds burnt-area polygons for layer 0 incidents and is only read for the
public advice text. Licence and terms: see docs/development/DATA_SOURCES.md.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Awaitable, Callable
import logging
from typing import Any
from urllib.parse import urlencode

from custom_components.ausnz_disaster_watch.const import STATE_NT
from custom_components.ausnz_disaster_watch.models import CanonicalHazard, HazardType, WarningLevel

from .base import MALFORMED_ITEM_ERRORS, BaseHazardProvider, ProviderUnavailableError, stable_id

_LOGGER = logging.getLogger(__name__)

NT_FIRE_INCIDENTS_URL = "https://gis-d.nt.gov.au/arcgis/rest/services/Hosted/Fire_Incidents/FeatureServer"
NT_ALERTS_URL = "https://securent.nt.gov.au/alerts"

# Point layers with one feature per incident: layer id -> label
NT_INCIDENT_LAYERS: dict[int, str] = {0: "NT Bushfires", 1: "NT Fire and Rescue"}
# Burnt-area polygons for layer 0 incidents; they carry the public advice text
NT_AREAS_LAYER = 2

# The service caps a response at 2000 records (maxRecordCount); active NT incidents are a
# few dozen at most, so one page is enough and an overflow is only logged.
_PAGE_SIZE = 2000
_QUERY = urlencode(
    {
        "where": "f_status='active'",
        "outFields": "*",
        "outSR": "4326",
        "f": "geojson",
        "resultRecordCount": _PAGE_SIZE,
    }
)
_AREAS_QUERY = urlencode(
    {
        "where": "f_status='active'",
        "outFields": "f_datenotified,f_eventtype,f_location,risks,what_to_do,current_situation",
        "returnGeometry": "false",
        "f": "geojson",
        "resultRecordCount": _PAGE_SIZE,
    }
)

# Advice fields copied from the area layer onto the matching incident
_ADVICE_FIELDS = ("risks", "what_to_do", "current_situation")


def _text(props: dict[str, Any], *keys: str) -> str:
    """Return the first non-empty value among ``keys`` as stripped text."""
    for key in keys:
        value = props.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def _incident_key(props: dict[str, Any]) -> tuple[str, str, str]:
    """Return the fields that identify one incident across layers."""
    return (
        _text(props, "f_datenotified"),
        _text(props, "f_eventtype", "fire_type"),
        _text(props, "f_location", "location"),
    )


class NTHazardProvider(BaseHazardProvider):
    """Provider for Northern Territory fire incidents (Bushfires NT and NTFRS)."""

    local_tz = "Australia/Darwin"

    @property
    def state_code(self) -> str:
        """Return jurisdiction identifier."""
        return STATE_NT

    async def async_fetch_hazards(self) -> list[CanonicalHazard]:
        """Fetch active incidents from the NT Government Fire_Incidents layers.

        Each point layer is a separate source: one failing layer keeps the other's
        incidents; both failing raises ProviderUnavailableError (#16).
        """
        advice = await self._async_fetch_advice()

        def _fetch(layer: int, label: str) -> Callable[[], Awaitable[list[Any]]]:
            return lambda: self._async_fetch_layer(layer, _QUERY, label)

        def _parse(layer: int) -> Callable[[list[Any]], list[CanonicalHazard]]:
            return lambda features: self._parse_features(features, layer, advice)

        hazards = await self.async_collect_sources(
            (label, _fetch(layer, label), _parse(layer)) for layer, label in NT_INCIDENT_LAYERS.items()
        )
        return self._disambiguate_ids(hazards)

    async def _async_fetch_layer(self, layer: int, query: str, label: str) -> list[Any]:
        """Query one layer and return its feature list, validating the response."""
        payload = await self.async_fetch_feed_json(f"{NT_FIRE_INCIDENTS_URL}/{layer}/query?{query}", label)
        if not isinstance(payload, dict) or "error" in payload or payload.get("type") != "FeatureCollection":
            raise ProviderUnavailableError(f"{label} returned an unexpected payload")
        features = self.require_list(payload, "features", label)
        properties = payload.get("properties")
        if payload.get("exceededTransferLimit") or (
            isinstance(properties, dict) and properties.get("exceededTransferLimit")
        ):
            _LOGGER.warning("%s returned more than %s incidents; only the first page is used", label, _PAGE_SIZE)
        return features

    async def _async_fetch_advice(self) -> dict[tuple[str, str, str], dict[str, Any]]:
        """Return public advice text from the area layer, keyed by incident; empty on failure."""
        try:
            features = await self._async_fetch_layer(NT_AREAS_LAYER, _AREAS_QUERY, "NT fire areas")
        except ProviderUnavailableError as err:
            _LOGGER.debug("NT fire area advice unavailable: %s", err)
            return {}
        advice: dict[tuple[str, str, str], dict[str, Any]] = {}
        for feat in features:
            props = feat.get("properties") if isinstance(feat, dict) else None
            if isinstance(props, dict):
                advice[_incident_key(props)] = {field: props.get(field) for field in _ADVICE_FIELDS}
        return advice

    def _parse_features(
        self,
        features: list[Any],
        layer: int,
        advice: dict[tuple[str, str, str], dict[str, Any]] | None = None,
    ) -> list[CanonicalHazard]:
        """Parse Fire_Incidents point features into hazards, skipping closed incidents."""
        hazards: list[CanonicalHazard] = []
        advice = advice or {}

        for feat in features:
            try:
                if not isinstance(feat, dict):
                    continue

                props = feat.get("properties") or {}
                # The server filter asks for active incidents; check again so a closed one is
                # never shown if the filter is ignored (#14)
                machine_status = _text(props, "f_status").lower()
                if (machine_status and machine_status != "active") or _text(props, "status").lower() == "closed":
                    continue

                centroid = self.calculate_centroid(feat.get("geometry") or {})
                if not centroid:
                    continue

                lat, lon = centroid
                notified, event_type, location = _incident_key(props)
                event_type = event_type or "Emergency Incident"
                location = location or "Northern Territory"
                alert_level_str = _text(props, "alert_level", "f_category").lower()

                is_hr = "hazard reduction" in event_type.lower() or "planned" in event_type.lower()

                if "emergency" in alert_level_str:
                    level = WarningLevel.EMERGENCY_WARNING
                elif "watch" in alert_level_str:
                    level = WarningLevel.WATCH_AND_ACT
                elif "advice" in alert_level_str:
                    level = WarningLevel.ADVICE
                else:
                    level = WarningLevel.INFORMATION

                # Stable across polls (#7). The service rebuilds the layer on each upload, so
                # objectid is not stable; use notified time + event type + location instead.
                # Coordinates are only a tie-breaker when the notified time is missing.
                item_id = (
                    stable_id("nt", notified, event_type, location)
                    if notified
                    else stable_id("nt", event_type, location, round(lat, 3), round(lon, 3))
                )

                hazards.append(
                    CanonicalHazard(
                        id=item_id,
                        source="NT Police, Fire and Emergency Services",
                        title=f"{event_type} - {location}",
                        hazard_type=HazardType.from_str(event_type),
                        warning_level=level,
                        latitude=lat,
                        longitude=lon,
                        updated_at=self.parse_datetime(props.get("f_lastupdate") or props.get("f_datenotified")),
                        location_name=location,
                        is_hazard_reduction=is_hr,
                        status=_text(props, "status") or "Active",
                        responsible_agency=_text(props, "responsible_agency") or "NT PFES",
                        web_url=NT_ALERTS_URL,
                        raw_properties={
                            "layer": NT_INCIDENT_LAYERS.get(layer, str(layer)),
                            **advice.get((notified, event_type, location), {}),
                        },
                    )
                )
            except MALFORMED_ITEM_ERRORS as err:
                _LOGGER.debug("Skipping malformed NT incident: %s", err)

        return hazards

    @staticmethod
    def _disambiguate_ids(hazards: list[CanonicalHazard]) -> list[CanonicalHazard]:
        """Give features that share every identifying field distinct IDs.

        Colliding features are separated by exact position, which does not depend on feed
        order. Only exact duplicates fall back to an order suffix.
        """
        counts = Counter(h.id for h in hazards)
        result: list[CanonicalHazard] = []
        seen: set[str] = set()
        for hazard in hazards:
            item_id = hazard.id
            if counts[item_id] > 1:
                item_id = stable_id(item_id, round(hazard.latitude, 6), round(hazard.longitude, 6))
            base_id, suffix = item_id, 2
            while item_id in seen:
                item_id = f"{base_id}_{suffix}"
                suffix += 1
            seen.add(item_id)
            result.append(hazard if item_id == hazard.id else hazard.model_copy(update={"id": item_id}))
        return result
