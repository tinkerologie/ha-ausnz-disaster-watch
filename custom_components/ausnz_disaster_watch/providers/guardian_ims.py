"""Client for council disaster dashboards built on Guardian IMS (QIT Plus) (#25).

About 60 Queensland councils and a handful of NSW councils publish the same Guardian IMS
dashboard. Each one serves JSON under ``<base>/dashboard/<endpoint>``, but not every
dashboard has every endpoint: a missing endpoint answers 404 (an HTML page). Several
endpoints return a JSON-encoded string that holds the real JSON document.

``GuardianDashboard`` hides those differences. It decodes double-encoded bodies, remembers
endpoints a dashboard does not have (each is asked again only after six hours), reuses
payloads within one poll, and maps the generic endpoints to the integration's models:

- power outages: ``ergonOutages`` (Ergon, regional QLD; ``Lat``/``Long`` are swapped) and
  ``energexOutages`` (Energex, south-east QLD);
- roads: ``imsRoad`` (council roads), ``moretonRoadClosures`` (Moreton Bay) and
  ``tmrRoadData`` (QLDTraffic events);
- relief facilities: ``imsEvac`` (evacuation centres, places of refuge, sandbag points),
  ``sandbagStations`` and ``moretonEvacs``;
- observations: ``getSurfaceObservation`` for the stations the dashboard's own weather
  widget lists, ``getWeatherStationsData`` (Moreton Bay), ``Currtemp`` as a fallback;
- air quality for the stations the dashboard's air-quality widget lists;
- cameras (``getCameras``), fire danger (``fireDangerRating``), the BoM warning summary
  (``bom``) and council bulletins (``imsBulletin``).

Endpoint shapes were verified against live dashboards on 2026-10-16.
"""

from __future__ import annotations

import contextlib
from datetime import UTC, datetime
import html
import json
import logging
import re
import time
from typing import TYPE_CHECKING, Any
from urllib.parse import quote, urlsplit

import aiohttp

from custom_components.ausnz_disaster_watch.models import (
    AirQualityStationData,
    DisasterCameraItem,
    EmergencyNewsItem,
    FireDangerRating,
    PowerOutageItem,
    ReliefFacilityItem,
    RoadClosureItem,
    WeatherStationObservation,
    WeatherWarningItem,
)

from .base import MALFORMED_ITEM_ERRORS, as_dict, stable_id

if TYPE_CHECKING:
    from .base import BaseHazardProvider

_LOGGER = logging.getLogger(__name__)

# Hosts that moved, or that are not Guardian IMS dashboards (None: no JSON dashboard).
# Saved entries keep their URL, so the alias is applied when the URL is read.
GUARDIAN_HOST_ALIASES: dict[str, str | None] = {
    "disaster.goldcoast.qld.gov.au": "dashboard.goldcoast.qld.gov.au",  # does not resolve
    "dashboard.cityofgoldcoast.com.au": "dashboard.goldcoast.qld.gov.au",  # 301 to the new host
    "disaster.redland.qld.gov.au": "dashboard.redland.qld.gov.au",  # 302 to the council website
    "disaster.sunshinecoast.qld.gov.au": None,  # Disaster Hub: a web app, not Guardian IMS
    "disasterhub.sunshinecoast.qld.gov.au": None,
    "disaster.brisbane.qld.gov.au": None,  # does not resolve
    "emergency.tweed.nsw.gov.au": None,  # not Guardian IMS (403 on every /dashboard path)
    "disaster.begavalley.nsw.gov.au": None,  # does not resolve
}

# Statuses meaning "this dashboard does not have the endpoint"; such an endpoint is not
# requested again for a while (a 403/404 can also be a temporary WAF block or deployment)
_UNAVAILABLE_STATUSES = frozenset({403, 404})
_UNAVAILABLE_TTL = 6 * 3600  # seconds

# getTemplateWidgets: a type 6 widget's "values" selects what it shows
_WIDGET_OBSERVATIONS = "4"
_WIDGET_AIR_QUALITY = "5"

_MS_DATE_RE = re.compile(r"/Date\((-?\d+)\)/")


def normalise_dashboard_url(url: Any) -> str | None:
    """Return the https base URL of a Guardian dashboard, or None if there is none.

    Known moved hosts are rewritten and known non-Guardian hosts are dropped.
    """
    if not url or not isinstance(url, str) or not url.strip():
        return None
    raw = url.strip()
    if "://" not in raw:
        raw = f"https://{raw}"
    parts = urlsplit(raw)
    host = (parts.hostname or "").lower()
    if not host:
        return None
    if host in GUARDIAN_HOST_ALIASES:
        alias = GUARDIAN_HOST_ALIASES[host]
        if alias is None:
            return None
        host = alias
    path = parts.path.rstrip("/")
    return f"https://{host}{path}"


def _decode(payload: Any) -> Any:
    """Decode a JSON-encoded string body; other values are returned unchanged."""
    if isinstance(payload, str):
        return json.loads(payload)
    return payload


def _features(payload: Any) -> list[dict[str, Any]]:
    """Return the features of a GeoJSON FeatureCollection, or [] for any other shape."""
    if isinstance(payload, dict) and isinstance(payload.get("features"), list):
        return [feat for feat in payload["features"] if isinstance(feat, dict)]
    return []


def _text(value: Any) -> str:
    """Return a clean display string (HTML entities decoded, whitespace trimmed)."""
    if value is None:
        return ""
    return html.unescape(str(value)).strip()


def _float(value: Any) -> float | None:
    """Return value as float, or None if it is missing or not numeric."""
    if value is None or value == "":
        return None
    with contextlib.suppress(TypeError, ValueError):
        return float(value)
    return None


def _bounded(value: Any, low: float, high: float) -> float | None:
    """Return a numeric value inside [low, high], or None."""
    number = _float(value)
    if number is None or not low <= number <= high:
        return None
    return number


def _lat_lon(lat: Any, lon: Any) -> tuple[float | None, float | None]:
    """Return a valid (lat, lon) pair; swapped pairs are corrected, invalid pairs give (None, None)."""
    flat, flon = _float(lat), _float(lon)
    if flat is None or flon is None:
        return None, None
    if abs(flat) > 90 >= abs(flon):
        # Ergon outages publish longitude in "Lat" and latitude in "Long"
        flat, flon = flon, flat
    if abs(flat) > 90 or abs(flon) > 180 or (abs(flat) < 0.001 and abs(flon) < 0.001):
        return None, None
    return flat, flon


def ms_date(value: Any) -> datetime | None:
    """Parse a .NET ``/Date(ms)/`` value or epoch milliseconds into an aware UTC datetime."""
    if isinstance(value, str) and (match := _MS_DATE_RE.search(value)):
        value = int(match.group(1))
    if isinstance(value, (int, float)) and not isinstance(value, bool) and value > 0:
        return datetime.fromtimestamp(value / 1000.0, tz=UTC)
    return None


class GuardianDashboard:
    """One council's Guardian IMS dashboard, fetched through its owning provider."""

    def __init__(self, provider: BaseHazardProvider, base_url: str) -> None:
        """Initialise the client for ``base_url`` (already normalised)."""
        self._provider = provider
        self.base_url = base_url
        self._unavailable: dict[str, float] = {}  # endpoint -> monotonic time it went missing
        self._poll_cache: dict[str, Any] = {}
        self._widget_details: list[dict[str, Any]] | None = None

    def start_poll(self) -> None:
        """Forget payloads from the previous poll."""
        self._poll_cache.clear()

    async def fetch(self, endpoint: str) -> Any | None:
        """Return the decoded payload of ``/dashboard/<endpoint>``, or None if there is none.

        None means the dashboard does not have the endpoint (not asked again for six hours) or
        the request failed this time (retried next poll). Successful payloads, empty ones
        included, are reused until the next poll.
        """
        if endpoint in self._poll_cache:
            return self._poll_cache[endpoint]
        if (since := self._unavailable.get(endpoint)) is not None:
            if time.monotonic() - since < _UNAVAILABLE_TTL:
                return None
            del self._unavailable[endpoint]
        url = f"{self.base_url}/dashboard/{endpoint}"
        try:
            payload = _decode(await self._provider.async_fetch_json(url))
        except aiohttp.ClientResponseError as err:
            if err.status in _UNAVAILABLE_STATUSES:
                _LOGGER.debug("Dashboard %s has no %s endpoint (HTTP %s)", self.base_url, endpoint, err.status)
                self._unavailable[endpoint] = time.monotonic()
            else:
                _LOGGER.debug("Error fetching %s: %s", url, err)
            return None
        except (aiohttp.ClientError, TimeoutError, ValueError) as err:
            _LOGGER.debug("Error fetching %s: %s", url, err)
            return None
        self._poll_cache[endpoint] = payload
        return payload

    async def _widget_station_ids(self, kind: str) -> str | None:
        """Return the comma-separated station IDs of the dashboard's widgets of ``kind``."""
        if self._widget_details is None:
            templates = await self.fetch("getTemplateWidgets")
            if not isinstance(templates, list):
                return None
            details: list[dict[str, Any]] = []
            for template in templates:
                widgets = template.get("widgets") if isinstance(template, dict) else None
                for widget in widgets if isinstance(widgets, list) else []:
                    with contextlib.suppress(*MALFORMED_ITEM_ERRORS):
                        detail = _decode(widget.get("details"))
                        if isinstance(detail, dict):
                            details.append(detail)
            self._widget_details = details
        ids: list[str] = []
        for detail in self._widget_details:
            if str(detail.get("type")) == "6" and str(detail.get("values")) == kind:
                for station in str(detail.get("stationIds") or "").split(","):
                    if (station := station.strip()) and station not in ids:
                        ids.append(station)
        return quote(",".join(ids), safe=",") or None

    # --- Power -----------------------------------------------------------------------

    async def power_outages(self) -> list[PowerOutageItem]:
        """Return Ergon and Energex outages; each network is only on the dashboards it serves."""
        outages: list[PowerOutageItem] = []
        ergon = await self.fetch("ergonOutages")
        for item in ergon if isinstance(ergon, list) else []:
            with contextlib.suppress(*MALFORMED_ITEM_ERRORS):
                lat, lon = _lat_lon(item.get("Lat"), item.get("Long"))
                suburbs = item.get("Suburbs")
                end = _text(item.get("End"))
                outages.append(
                    PowerOutageItem(
                        suburb=", ".join(str(s) for s in suburbs) if isinstance(suburbs, list) else _text(suburbs),
                        cause=_text(item.get("Reason")) or "Under Investigation",
                        restore_time=end if end and end.lower() != "unknown" else None,
                        customers_affected=int(_float(item.get("Customers")) or 0),
                        latitude=lat,
                        longitude=lon,
                    )
                )
        energex = await self.fetch("energexOutages")
        for model in energex if isinstance(energex, list) else []:
            with contextlib.suppress(*MALFORMED_ITEM_ERRORS):
                outage = model.get("Outage", model)
                restore = ms_date(outage.get("restoreTime"))
                outages.append(
                    PowerOutageItem(
                        suburb=_text(outage.get("suburb")),
                        cause=_text(outage.get("cause")) or "Under Investigation",
                        restore_time=restore.isoformat() if restore else None,
                        customers_affected=int(_float(outage.get("customersAffected")) or 0),
                    )
                )
        return outages

    # --- Roads -----------------------------------------------------------------------

    async def road_closures(self) -> list[RoadClosureItem]:
        """Return council road closures and QLDTraffic events near the council."""
        closures: list[RoadClosureItem] = []
        seen: set[str] = set()

        def add(item: RoadClosureItem) -> None:
            if item.id not in seen:
                seen.add(item.id)
                closures.append(item)

        for feat in _features(await self.fetch("imsRoad")):
            with contextlib.suppress(*MALFORMED_ITEM_ERRORS):
                add(self._parse_event(feat, "COUNCIL", "Local Council"))
        for feat in _features(await self.fetch("moretonRoadClosures")):
            with contextlib.suppress(*MALFORMED_ITEM_ERRORS):
                add(self._parse_moreton_road(feat))
        tmr = await self.fetch("tmrRoadData")
        for feat in tmr if isinstance(tmr, list) else []:
            with contextlib.suppress(*MALFORMED_ITEM_ERRORS):
                add(self._parse_event(feat, "TMR", "Department of Transport and Main Roads"))
        return closures

    def _parse_event(self, feat: dict[str, Any], prefix: str, default_source: str) -> RoadClosureItem:
        """Map a QLDTraffic-style road event (imsRoad, tmrRoadData) to a RoadClosureItem."""
        props = feat["properties"]
        if props.get("status") == "Reopened":
            raise ValueError("reopened road event")  # skipped like a malformed item
        raw_id = props.get("id") or feat.get("id")
        if not raw_id:
            raise ValueError("road event without id")
        centroid = self._provider.calculate_centroid(feat.get("geometry") or {})
        lat, lon = _lat_lon(*centroid) if centroid else (None, None)
        summary = as_dict(props.get("road_summary"))
        impact = as_dict(props.get("impact"))
        source = as_dict(props.get("source"))
        subtype = _text(props.get("event_subtype"))
        return RoadClosureItem(
            id=f"{prefix}_{raw_id}",
            road=_text(props.get("road") or summary.get("road_name") or props.get("event_type") or "Road"),
            suburb=_text(props.get("suburb") or summary.get("locality")),
            status=_text(impact.get("impact_subtype") or props.get("event_type")) or "Hazard",
            reason=_text(props.get("event_due_to")) or subtype or None,
            description=_text(props.get("description")) or None,
            advice=_text(props.get("advice")) or None,
            source=_text(source.get("provided_by")) or default_source,
            updated_at=self._provider.parse_datetime(props.get("last_updated")),
            latitude=lat,
            longitude=lon,
        )

    def _parse_moreton_road(self, feat: dict[str, Any]) -> RoadClosureItem:
        """Map a Moreton Bay ``moretonRoadClosures`` feature to a RoadClosureItem."""
        props = feat["properties"]
        raw_id = props.get("ID") or props.get("OBJECTID") or feat.get("id")
        if not raw_id:
            raise ValueError("road closure without id")
        centroid = self._provider.calculate_centroid(feat.get("geometry") or {})
        return RoadClosureItem(
            id=f"COUNCIL_{raw_id}",
            road=_text(props.get("ROAD")) or "Local Road",
            suburb=_text(props.get("SUBURB")),
            status=_text(props.get("STATUS")) or "Closed",
            reason=_text(props.get("REASON")) or None,
            description=_text(props.get("DESCRIPTION")) or None,
            source="Local Council",
            updated_at=ms_date(props.get("UPDATETIME")),
            latitude=centroid[0] if centroid else None,
            longitude=centroid[1] if centroid else None,
        )

    # --- Relief facilities --------------------------------------------------------------

    async def relief_facilities(self) -> list[ReliefFacilityItem]:
        """Return evacuation centres, places of refuge and sandbag points."""
        facilities: list[ReliefFacilityItem] = []
        for feat in _features(await self.fetch("imsEvac")):
            with contextlib.suppress(*MALFORMED_ITEM_ERRORS):
                facilities.append(self._parse_ims_evac(feat))
        for endpoint, kind, default_name in (
            ("sandbagStations", "sandbag_station", "Sandbag Station"),
            ("moretonEvacs", "evacuation_centre", "Evacuation Centre"),
        ):
            for feat in _features(await self.fetch(endpoint)):
                with contextlib.suppress(*MALFORMED_ITEM_ERRORS):
                    facilities.append(self._parse_legacy_facility(feat, kind, default_name))
        return facilities

    def _parse_ims_evac(self, feat: dict[str, Any]) -> ReliefFacilityItem:
        """Map an ``imsEvac`` feature; its building type says what kind of facility it is."""
        props = feat["properties"]
        building_type = _text(props.get("buildingtype")).lower()
        if "sandbag" in building_type:
            kind = "sandbag_station"
        elif "refuge" in building_type:
            kind = "place_of_refuge"
        else:
            kind = "evacuation_centre"
        name = _text(props.get("buildingname")) or "Relief Facility"
        address = _text(props.get("buildingaddress"))
        centroid = self._provider.calculate_centroid(feat.get("geometry") or {})
        raw_id = feat.get("id") or props.get("id")
        return ReliefFacilityItem(
            id=f"ims_{raw_id}" if raw_id else stable_id("ims", props.get("organisation"), name, address),
            facility_type=kind,
            name=name,
            address=address,
            status=_text(props.get("status")) or "Unknown",
            latitude=centroid[0] if centroid else None,
            longitude=centroid[1] if centroid else None,
        )

    def _parse_legacy_facility(self, feat: dict[str, Any], kind: str, default_name: str) -> ReliefFacilityItem:
        """Map a ``sandbagStations``/``moretonEvacs`` feature (ArcGIS upper-case fields)."""
        props = feat["properties"]
        centroid = self._provider.calculate_centroid(feat.get("geometry") or {})
        prefix = "sandbag" if kind == "sandbag_station" else "evac"
        object_id = props.get("OBJECTID") or feat.get("id")
        return ReliefFacilityItem(
            id=f"{prefix}_{object_id or stable_id('qld_relief', props.get('NAME'), centroid)}",
            facility_type=kind,
            name=_text(props.get("NAME")) or default_name,
            suburb=_text(props.get("SUBURB")),
            address=_text(props.get("ADDRESS")),
            status=_text(props.get("STATUS")) or "Open",
            latitude=centroid[0] if centroid else None,
            longitude=centroid[1] if centroid else None,
        )

    # --- Weather and environment --------------------------------------------------------

    async def weather_telemetry(self) -> list[WeatherStationObservation]:
        """Return the dashboard's weather observations."""
        stations: list[WeatherStationObservation] = []
        if station_ids := await self._widget_station_ids(_WIDGET_OBSERVATIONS):
            observations = await self.fetch(f"getSurfaceObservation?ObsId={station_ids}")
            for obs in observations if isinstance(observations, list) else []:
                with contextlib.suppress(*MALFORMED_ITEM_ERRORS):
                    stations.append(self._parse_surface_observation(obs))

        council_stations = await self.fetch("getWeatherStationsData")
        for station in council_stations if isinstance(council_stations, list) else []:
            with contextlib.suppress(*MALFORMED_ITEM_ERRORS):
                stations.append(self._parse_council_station(station))

        if not stations:
            current = await self.fetch("Currtemp")
            if isinstance(current, dict) and (air := _float(current.get("air_temp"))) is not None:
                stations.append(
                    WeatherStationObservation(
                        station_id="currtemp",
                        station_name="Current Conditions",
                        temperature=air,
                        apparent_temperature=_float(current.get("apparent_t")),
                    )
                )
        return stations

    @staticmethod
    def _parse_surface_observation(obs: dict[str, Any]) -> WeatherStationObservation:
        """Map a BoM surface observation (``getSurfaceObservation``)."""
        name = _text(obs.get("msstnname") or obs.get("msstnaltname"))
        if not name:
            raise ValueError("observation without station name")
        return WeatherStationObservation(
            station_id=_text(obs.get("msbomid") or obs.get("mswmoid") or obs.get("Id")) or name,
            station_name=name.title(),
            temperature=_float(obs.get("msairtemp")),
            apparent_temperature=_float(obs.get("msapptemp")),
            relative_humidity=_bounded(obs.get("msrelhum"), 0, 100),
            pressure_hpa=_float(obs.get("msmslpres")),
            wind_direction=_bounded(obs.get("mswinddirdeg"), 0, 360),
            wind_speed_avg=_bounded(obs.get("mswindspdkmh"), 0, 500),
            wind_speed_max=_bounded(obs.get("msgustkmh"), 0, 500),
            rain_since_9am=_bounded(obs.get("msrain"), 0, 5000),
        )

    @staticmethod
    def _parse_council_station(station: dict[str, Any]) -> WeatherStationObservation:
        """Map a council-owned station (Moreton Bay ``getWeatherStationsData``)."""
        metrics: dict[str, float] = {}
        for item in station.get("weatherData") or []:
            if isinstance(item, dict) and item.get("name") and (value := _float(item.get("currentValue"))) is not None:
                metrics[str(item["name"])] = value
        return WeatherStationObservation(
            station_id=_text(station.get("id")),
            station_name=_text(station.get("name")) or "Weather Station",
            temperature=metrics.get("TenMin - AirTC"),
            relative_humidity=_bounded(metrics.get("TenMin - RH"), 0, 100),
            pressure_hpa=metrics.get("TenMin - BP hPa"),
            wind_direction=_bounded(metrics.get("Hourly - WindDir-Avg-Vect"), 0, 360),
            wind_speed_avg=_bounded(metrics.get("Hourly - ws-kph-Avg"), 0, 500),
            wind_speed_max=_bounded(metrics.get("Hourly - ws-kph-Max"), 0, 500),
            solar_radiation=metrics.get("TenMin - SlrW"),
        )

    async def air_quality(self) -> list[AirQualityStationData]:
        """Return air quality for the stations the dashboard's air-quality widget lists."""
        station_ids = await self._widget_station_ids(_WIDGET_AIR_QUALITY)
        if not station_ids:
            return []
        payload = await self.fetch(f"airQuality?stationIds={station_ids}")
        items = payload.get("AirQualityStationDataList") if isinstance(payload, dict) else None
        stations: list[AirQualityStationData] = []
        for item in items if isinstance(items, list) else []:
            with contextlib.suppress(*MALFORMED_ITEM_ERRORS):
                stations.append(
                    AirQualityStationData(
                        station_id=_text(item.get("station_id")),
                        station_name=_text(item.get("station_name")) or "Air Station",
                        pm2_5_measurement=item.get("PM2_5_Measurement") or None,
                        pm2_5_rating=item.get("PM2_5_Rating") or None,
                        pm2_5_running_average=item.get("PM2_5_Running_Average") or None,
                        pm10_measurement=item.get("PM10_Measurement") or None,
                        pm10_rating=item.get("PM10_Rating") or None,
                        pm10_running_average=item.get("PM10_Running_Average") or None,
                        no2_measurement=item.get("NO2_Measurement") or None,
                        no2_rating=item.get("NO2_Rating") or None,
                        o3_measurement=item.get("O3_Measurement") or None,
                        o3_rating=item.get("O3_Rating") or None,
                        overall_rating=str(item.get("PM2_5_Rating") or item.get("PM10_Rating") or "Good"),
                    )
                )
        return stations

    async def fire_danger(self) -> FireDangerRating | None:
        """Return the district fire danger rating and the forecast day it applies to.

        The feed has no total fire ban field, so ``total_fire_ban`` stays unknown (None)
        unless a ``TOBAN`` value is present.
        """
        payload = await self.fetch("fireDangerRating")
        data = payload.get("Data") if isinstance(payload, dict) else None
        if not isinstance(data, list) or not data or not isinstance(data[0], dict):
            return None
        first = data[0]
        toban = first.get("TOBAN")
        return FireDangerRating(
            district_number=_text(first.get("District_Number")),
            district_name=_text(first.get("District_Name")),
            rating=_text(first.get("FDR")) or "Moderate",
            total_fire_ban=None if toban is None else str(toban).strip().lower() in ("yes", "true", "1"),
            day=_text(first.get("Day")) or None,
        )

    async def weather_warnings(self) -> list[WeatherWarningItem]:
        """Return the BoM warning summary for the council's forecast district.

        These warnings carry no geometry, so they are a summary list, never hazards placed
        at a location.
        """
        payload = await self.fetch("bom")
        items = payload.get("item") if isinstance(payload, dict) else None
        warnings: list[WeatherWarningItem] = []
        for item in items if isinstance(items, list) else []:
            with contextlib.suppress(*MALFORMED_ITEM_ERRORS):
                if title := _text(item.get("title")):
                    warnings.append(
                        WeatherWarningItem(
                            title=title,
                            link=item.get("link") or None,
                            locations=_text(item.get("locations")) or None,
                            pub_date=self._provider.parse_datetime(item.get("pubDate")),
                        )
                    )
        return warnings

    async def bulletins(self) -> list[dict[str, Any]]:
        """Return the council bulletin features (``imsBulletin``)."""
        return _features(await self.fetch("imsBulletin"))

    async def emergency_news(self) -> list[EmergencyNewsItem]:
        """Return council bulletins as news items."""
        news: list[EmergencyNewsItem] = []
        for feat in await self.bulletins():
            with contextlib.suppress(*MALFORMED_ITEM_ERRORS):
                props = feat["properties"]
                title = _text(props.get("title") or props.get("headline")) or "Disaster News"
                created = props.get("created") or props.get("updated")
                raw_id = props.get("id") or props.get("bulletin_id")
                news.append(
                    EmergencyNewsItem(
                        id=str(raw_id) if raw_id else stable_id("bulletin", title, created),
                        title=title,
                        description=props.get("description") or props.get("content"),
                        link=props.get("url"),
                        pub_date=self._provider.parse_datetime(created),
                    )
                )
        return news

    async def cameras(self) -> list[DisasterCameraItem]:
        """Return the dashboard's flood and traffic cameras (``getCameras``)."""
        cameras: list[DisasterCameraItem] = []
        host = urlsplit(self.base_url).hostname
        for feat in _features(await self.fetch("getCameras")):
            with contextlib.suppress(*MALFORMED_ITEM_ERRORS):
                props = feat["properties"]
                # Some cameras list several snapshot URLs separated by commas
                image_url = next(
                    (u.strip() for u in str(props.get("image_url") or "").split(",") if u.strip().startswith("http")),
                    None,
                )
                if not image_url or not props.get("id"):
                    continue
                centroid = self._provider.calculate_centroid(feat.get("geometry") or {})
                lat, lon = _lat_lon(*centroid) if centroid else (None, None)
                cameras.append(
                    DisasterCameraItem(
                        id=stable_id("camera", host, props["id"]),
                        name=_text(props.get("description")) or _text(props.get("typeName")) or "Camera",
                        image_url=image_url,
                        suburb=_text(props.get("locality")) or None,
                        latitude=lat,
                        longitude=lon,
                    )
                )
        return cameras
