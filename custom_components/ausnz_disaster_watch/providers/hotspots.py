"""Digital Earth Australia (Geoscience Australia) satellite hotspots near the configured location.

Hotspots are satellite detections of heat sources. They are not fire warnings and may be
industrial heat, burns or false detections, so they are exposed as an informational count,
never as hazards or warning levels. Data: DEA Hotspots, CC BY 4.0; not for safety-of-life
decisions.

The WFS query is always limited to a bounding box around the monitoring radius, the last
24 hours and a minimum confidence, with a feature cap; the full national file is never
downloaded. ``DescribeFeatureType`` names the geometry ``geometry`` (``location`` also
works) in EPSG:4326. GeoServer reads ``BBOX(..., 'EPSG:4326')`` as latitude/longitude, so
the box is given explicitly as ``CRS:84`` (longitude/latitude); verified 2026-10-16.
"""

from __future__ import annotations

import math
from typing import Any
from urllib.parse import urlencode

from custom_components.ausnz_disaster_watch.models import SatelliteHotspotItem, SatelliteHotspots

from .base import MALFORMED_ITEM_ERRORS, BaseHazardProvider, stable_id
from .cap import haversine_km

DEA_WFS_URL = "https://hotspots.dea.ga.gov.au/geoserver/public/wfs"
DEA_LAYER = "public:hotspots_three_days"
HOTSPOT_MAX_AGE_HOURS = 24
HOTSPOT_MIN_CONFIDENCE = 50
HOTSPOT_FEATURE_LIMIT = 500
_KM_PER_DEGREE = 111.32
_PROPERTIES = "id,location,confidence,power,temp_kelvin,hours_since_hotspot,satellite,datetime"


def hotspot_query_url(lat: float, lon: float, radius_km: float) -> str:
    """Return the bounded WFS GetFeature URL for hotspots around a point."""
    d_lat = radius_km / _KM_PER_DEGREE
    d_lon = radius_km / (_KM_PER_DEGREE * max(math.cos(math.radians(lat)), 0.01))
    bbox = f"{lon - d_lon:.4f},{lat - d_lat:.4f},{lon + d_lon:.4f},{lat + d_lat:.4f}"
    params = {
        "service": "WFS",
        "version": "2.0.0",
        "request": "GetFeature",
        "typeNames": DEA_LAYER,
        "outputFormat": "application/json",
        "count": str(HOTSPOT_FEATURE_LIMIT),
        "propertyName": _PROPERTIES,
        "CQL_FILTER": (
            f"hours_since_hotspot<{HOTSPOT_MAX_AGE_HOURS} AND confidence>={HOTSPOT_MIN_CONFIDENCE}"
            f" AND BBOX(location,{bbox},'CRS:84')"
        ),
    }
    return f"{DEA_WFS_URL}?{urlencode(params)}"


def _number(value: Any) -> float | None:
    """Return a measurement, or None for missing values and the feed's negative sentinels (-1, -999)."""
    if value is None or isinstance(value, bool):
        return None
    number = float(value)
    return number if number >= 0 else None


def parse_hotspots(payload: Any, lat: float, lon: float, radius_km: float) -> SatelliteHotspots:
    """Return hotspots within the radius, nearest first."""
    data = BaseHazardProvider.require_dict(payload, "DEA hotspots")
    features = BaseHazardProvider.require_list(data, "features", "DEA hotspots")
    items: list[SatelliteHotspotItem] = []
    for feature in features:
        try:
            props = feature.get("properties") or {}
            point = BaseHazardProvider.calculate_centroid(feature.get("geometry") or {})
            if point is None:
                continue
            distance = haversine_km(lat, lon, point[0], point[1])
            if distance > radius_km:
                continue
            upstream_id = props.get("id")
            items.append(
                SatelliteHotspotItem(
                    id=f"DEA_{upstream_id}"
                    if upstream_id is not None
                    else stable_id("DEA", *point, props.get("datetime")),
                    latitude=point[0],
                    longitude=point[1],
                    confidence=_number(props.get("confidence")),
                    power=_number(props.get("power")),
                    temp_kelvin=_number(props.get("temp_kelvin")),
                    hours_since_hotspot=_number(props.get("hours_since_hotspot")),
                    observed_at=BaseHazardProvider.parse_datetime(props.get("datetime"), "UTC"),
                    satellite=(str(props["satellite"]).strip() or None) if props.get("satellite") else None,
                    distance_km=round(distance, 1),
                )
            )
        except MALFORMED_ITEM_ERRORS:
            continue
    matched, returned = data.get("numberMatched"), data.get("numberReturned")
    truncated = isinstance(matched, int) and isinstance(returned, int) and matched > returned
    items.sort(key=lambda item: item.distance_km or 0.0)
    return SatelliteHotspots(items=items, min_confidence=HOTSPOT_MIN_CONFIDENCE, truncated=truncated)
