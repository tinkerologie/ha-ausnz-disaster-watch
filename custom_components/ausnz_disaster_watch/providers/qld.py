"""Queensland emergency hazards provider (QFD & Council Disaster Dashboards)."""

from __future__ import annotations

import contextlib
import hashlib
import json
import logging
from typing import Any

from custom_components.ausnz_disaster_watch.const import CONF_COUNCIL_DASHBOARD_URL, STATE_QLD
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

from .base import BaseHazardProvider, stable_id

_LOGGER = logging.getLogger(__name__)

QFD_WARNINGS_URL = (
    "https://publiccontent-gis-psba-qld-gov-au.s3.amazonaws.com"
    "/content/Feeds/BushfireCurrentIncidents/bushfireAlert.json"
)
DEFAULT_QLD_COUNCIL_URL = "https://disaster.moretonbay.qld.gov.au"


class QueenslandHazardProvider(BaseHazardProvider):
    """Provider for Queensland Fire Department and Local Disaster Dashboards."""

    local_tz = "Australia/Brisbane"

    @property
    def state_code(self) -> str:
        """Return state code."""
        return STATE_QLD

    async def async_fetch_hazards(self) -> list[CanonicalHazard]:
        """Fetch hazards from QFD and optional Council Disaster Dashboard."""
        self._payload_cache.clear()
        hazards: list[CanonicalHazard] = []
        seen_ids: set[str] = set()

        # 1. Fetch State-wide QFD Public Warnings feed
        try:
            qfd_data = await self.async_fetch_json(QFD_WARNINGS_URL)
            if qfd_data and isinstance(qfd_data, dict):
                features = qfd_data.get("features", [])
                for feature in features:
                    hazard = self._parse_qfd_feature(feature)
                    if hazard and hazard.id not in seen_ids:
                        seen_ids.add(hazard.id)
                        hazards.append(hazard)
        except Exception as err:  # noqa: BLE001
            _LOGGER.warning("Error fetching Queensland Fire Department warnings feed: %s", err)

        # 2. Fetch Council Disaster Dashboard feeds if URL configured
        base_url = self._get_council_base_url()
        if base_url:
            hazards.extend(await self._fetch_council_hazards(base_url, seen_ids))

        return hazards

    async def _fetch_council_hazards(self, base_url: str, seen_ids: set[str]) -> list[CanonicalHazard]:
        """Fetch auxiliary hazards from council disaster dashboard feeds."""
        hazards: list[CanonicalHazard] = []

        # 2a. Detailed Fire Incidents
        try:
            fire_data = await self.async_fetch_json(f"{base_url}/dashboard/fireDetailed")
            if isinstance(fire_data, list):
                for item in fire_data:
                    hazard = self._parse_council_fire_item(item)
                    if hazard and hazard.id not in seen_ids:
                        seen_ids.add(hazard.id)
                        hazards.append(hazard)
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("Error fetching council fire incidents from %s: %s", base_url, err)

        # 2b. Road Hazards and Closures
        try:
            tmr_url = f"{base_url}/dashboard/tmrRoadData"
            road_data = await self.async_fetch_json(tmr_url)
            if road_data:
                self._payload_cache[tmr_url] = road_data
            if isinstance(road_data, list):
                for item in road_data:
                    hazard = self._parse_council_road_item(item)
                    if hazard and hazard.id not in seen_ids:
                        seen_ids.add(hazard.id)
                        hazards.append(hazard)
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("Error fetching council road conditions from %s: %s", base_url, err)

        # 2c. Weather Warnings (BoM)
        try:
            bom_url = f"{base_url}/dashboard/bom"
            bom_data = await self.async_fetch_json(bom_url)
            if bom_data:
                self._payload_cache[bom_url] = bom_data
            if isinstance(bom_data, dict):
                items = bom_data.get("item", [])
                if isinstance(items, list):
                    for item in items:
                        hazard = self._parse_council_bom_item(item)
                        if hazard and hazard.id not in seen_ids:
                            seen_ids.add(hazard.id)
                            hazards.append(hazard)
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("Error fetching council weather warnings from %s: %s", base_url, err)

        # 2d. Council Bulletins
        try:
            bulletin_url = f"{base_url}/dashboard/imsBulletin"
            bulletin_data = await self.async_fetch_json(bulletin_url)
            if bulletin_data:
                self._payload_cache[bulletin_url] = bulletin_data
            if isinstance(bulletin_data, dict):
                features = bulletin_data.get("features", [])
                for feat in features:
                    hazard = self._parse_council_bulletin_feature(feat)
                    if hazard and hazard.id not in seen_ids:
                        seen_ids.add(hazard.id)
                        hazards.append(hazard)
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("Error fetching council bulletins from %s: %s", base_url, err)

        return hazards

    def _parse_qfd_feature(self, feature: dict[str, Any]) -> CanonicalHazard | None:
        """Parse feature from QFD bushfireAlert.json."""
        properties = feature.get("properties", {})
        geometry = feature.get("geometry", {})
        centroid = self.calculate_centroid(geometry)
        if not centroid:
            return None

        lat, lon = centroid
        raw_uid = properties.get("UniqueID") or properties.get("OBJECTID") or properties.get("Incident_Number")
        if not raw_uid:
            return None
        unique_id = str(raw_uid).strip()
        if not unique_id:
            return None

        title = str(
            properties.get("WarningTitle") or properties.get("Incident_Name") or "Queensland Fire Incident"
        ).strip()

        raw_level = properties.get("WarningLevel") or properties.get("Alert_Level")
        warning_level = WarningLevel.from_str(str(raw_level))

        raw_type = properties.get("Incident_Type") or properties.get("HazardType") or "Bushfire"
        hazard_type = HazardType.from_str(str(raw_type))

        updated_at = self.parse_datetime(
            properties.get("LastUpdate") or properties.get("Updated") or properties.get("Response_Date")
        )

        location_name = str(
            properties.get("Location")
            or properties.get("Location_Name")
            or properties.get("CallToAction")
            or "Queensland"
        ).strip()

        is_hazard_reduction = bool(
            "hazard reduction" in title.lower()
            or "planned burn" in title.lower()
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
            status=properties.get("Status") or properties.get("CurrentStatus"),
            responsible_agency=properties.get("Agency") or "QFD",
            web_url=properties.get("Web_URL") or "https://www.fire.qld.gov.au/Current-Incidents",
            raw_properties=properties,
        )

    def _parse_council_fire_item(self, item: dict[str, Any]) -> CanonicalHazard | None:
        """Parse fire item from Guardian IMS /dashboard/fireDetailed."""
        props = item.get("properties", {})
        lat = props.get("Latitude")
        lon = props.get("Longitude")
        if lat is None or lon is None:
            # Check geometry
            centroid = self.calculate_centroid(item.get("geometry", {}))
            if centroid:
                lat, lon = centroid
            else:
                return None

        try:
            flat = float(lat)
            flon = float(lon)
            if abs(flat) < 0.001 and abs(flon) < 0.001:
                return None
        except (ValueError, TypeError):
            return None

        raw_inc = props.get("Master_Incident_Number") or props.get("MIN_ID") or item.get("id")
        if not raw_inc or str(raw_inc) == "0":
            return None
        inc_id = str(raw_inc)

        title = str(
            props.get("Location_Name")
            or props.get("Location")
            or props.get("name")
            or props.get("Incident_Type")
            or "Incident"
        ).strip()

        hazard_type = HazardType.from_str(props.get("Incident_Type") or props.get("SubType"))
        warning_level = WarningLevel.from_str(props.get("Alert_Level") or props.get("CurrentStatus"))
        if warning_level == WarningLevel.UNKNOWN:
            warning_level = WarningLevel.INFORMATION

        updated_at = self.parse_datetime(props.get("LastUpdate") or props.get("Response_Date"))
        location_name = str(props.get("LGA") or props.get("Location_Name") or "").strip()

        is_hazard_reduction = bool(
            "hazard reduction" in str(props.get("Incident_Type", "")).lower()
            or "permitted burn" in str(props.get("Incident_Type", "")).lower()
        )

        return CanonicalHazard(
            id=f"QLD_COUNCIL_FIRE_{inc_id}",
            source="Council Disaster Dashboard",
            title=title,
            hazard_type=hazard_type,
            warning_level=warning_level,
            latitude=flat,
            longitude=flon,
            updated_at=updated_at,
            location_name=location_name,
            is_hazard_reduction=is_hazard_reduction,
            status=props.get("CurrentStatus"),
            responsible_agency=props.get("Jurisdiction") or "Emergency Services",
            web_url=props.get("Web_URL"),
            raw_properties=props,
        )

    def _parse_council_road_item(self, item: dict[str, Any]) -> CanonicalHazard | None:
        """Parse road condition/hazard from Guardian IMS /dashboard/tmrRoadData."""
        props = item.get("properties", {})
        geometry = item.get("geometry", {})
        centroid = self.calculate_centroid(geometry)
        if not centroid:
            return None

        lat, lon = centroid
        raw_road_id = props.get("id") or item.get("id")
        if not raw_road_id:
            return None
        road_id = str(raw_road_id)

        event_type = props.get("event_type", "Hazard")
        impact = props.get("impact", {})
        impact_subtype = impact.get("impact_subtype", "") if isinstance(impact, dict) else ""
        title = f"{event_type}: {impact_subtype}".strip(": ") if impact_subtype else str(event_type)

        duration = props.get("duration", {})
        start_time = duration.get("start") if isinstance(duration, dict) else None
        updated_at = self.parse_datetime(props.get("published") or start_time)

        status = props.get("status", "Active")
        if status == "Reopened":
            return None

        # Road hazards are typically information / advice level
        warning_level = WarningLevel.ADVICE if "closed" in impact_subtype.lower() else WarningLevel.INFORMATION

        source_info = props.get("source", {})
        agency = source_info.get("provided_by") if isinstance(source_info, dict) else "QLDTraffic / Council"

        return CanonicalHazard(
            id=f"QLD_COUNCIL_ROAD_{road_id}",
            source="QLDTraffic / Council",
            title=title,
            hazard_type=HazardType.ROAD_INCIDENT,
            warning_level=warning_level,
            latitude=lat,
            longitude=lon,
            updated_at=updated_at,
            location_name=props.get("suburb") or props.get("road_name") or "Queensland",
            status=status,
            responsible_agency=agency,
            web_url=props.get("url") or "https://qldtraffic.qld.gov.au",
            raw_properties=props,
        )

    def _parse_council_bom_item(self, item: dict[str, Any]) -> CanonicalHazard | None:
        """Parse Bureau of Meteorology warning item from /dashboard/bom."""
        title = str(item.get("title", "")).strip()
        if not title:
            return None

        link = str(item.get("link", ""))
        locations = str(item.get("locations", ""))
        updated_at = self.parse_datetime(item.get("pubDate"))

        # Infer hazard type and warning level from title
        hazard_type = HazardType.from_str(title)
        warning_level = WarningLevel.from_str(title)
        if warning_level == WarningLevel.UNKNOWN:
            # BoM warnings are at least Advice / Watch and Act
            if "severe" in title.lower() or "flood" in title.lower() or "cyclone" in title.lower():
                warning_level = WarningLevel.WATCH_AND_ACT
            else:
                warning_level = WarningLevel.ADVICE

        # Derive stable ID
        id_hash = hashlib.md5(f"{title}_{link}".encode()).hexdigest()[:10]

        # Use configured location latitude/longitude if no geometry in BoM item
        lat = float(self.config.get("latitude", -27.2657))
        lon = float(self.config.get("longitude", 152.9818))

        return CanonicalHazard(
            id=f"QLD_COUNCIL_BOM_{id_hash}",
            source="Bureau of Meteorology",
            title=title,
            hazard_type=hazard_type,
            warning_level=warning_level,
            latitude=lat,
            longitude=lon,
            updated_at=updated_at,
            location_name=locations[:100] if locations else "Queensland",
            responsible_agency="Bureau of Meteorology",
            web_url=link or "http://www.bom.gov.au/qld/warnings/",
            raw_properties=item,
        )

    def _parse_council_bulletin_feature(self, feature: dict[str, Any]) -> CanonicalHazard | None:
        """Parse council emergency bulletin from /dashboard/imsBulletin."""
        props = feature.get("properties", {})
        geometry = feature.get("geometry", {})
        centroid = self.calculate_centroid(geometry)

        lat = centroid[0] if centroid else float(self.config.get("latitude", -27.2657))
        lon = centroid[1] if centroid else float(self.config.get("longitude", 152.9818))

        raw_id = props.get("id") or props.get("bulletin_id")
        if not raw_id:
            return None
        bulletin_id = str(raw_id)

        title = str(props.get("title") or props.get("headline") or "Council Disaster Bulletin").strip()
        warning_level = WarningLevel.from_str(props.get("priority") or props.get("level"))
        if warning_level == WarningLevel.UNKNOWN:
            warning_level = WarningLevel.ADVICE

        return CanonicalHazard(
            id=f"QLD_COUNCIL_BULLETIN_{bulletin_id}",
            source="Council Disaster Operations",
            title=title,
            hazard_type=HazardType.OTHER,
            warning_level=warning_level,
            latitude=lat,
            longitude=lon,
            updated_at=self.parse_datetime(props.get("created") or props.get("updated")),
            location_name=props.get("suburb") or "Moreton Bay",
            status="Active",
            responsible_agency="Local Disaster Management Group",
            web_url=props.get("url"),
            raw_properties=props,
        )

    def _get_council_base_url(self) -> str | None:
        """Return configured Queensland Council Disaster Dashboard base URL or None."""
        url = self.config.get(CONF_COUNCIL_DASHBOARD_URL)
        if not url:
            return None
        return str(url).strip().rstrip("/")

    async def async_fetch_power_outages(self) -> list[PowerOutageItem]:
        """Fetch real-time power outages from Energex / Ergon network feed."""
        base_url = self._get_council_base_url()
        if not base_url:
            return []
        outages: list[PowerOutageItem] = []
        try:
            data = await self.async_fetch_json(f"{base_url}/dashboard/energexOutages")
            if isinstance(data, list):
                for model in data:
                    if not isinstance(model, dict):
                        continue
                    outage_obj = model.get("Outage", {}) if "Outage" in model else model
                    suburb = str(outage_obj.get("suburb") or "")
                    cause = str(outage_obj.get("cause") or "Under Investigation")
                    restore_time = outage_obj.get("restoreTime")
                    customers = int(outage_obj.get("customersAffected") or 0)
                    outages.append(
                        PowerOutageItem(
                            suburb=suburb,
                            cause=cause,
                            restore_time=str(restore_time) if restore_time else None,
                            customers_affected=customers,
                        )
                    )
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("Error fetching Queensland power outages: %s", err)
        return outages

    async def async_fetch_road_closures(self) -> list[RoadClosureItem]:
        """Fetch road closures from Local Council and TMR/QLDTraffic feeds."""
        base_url = self._get_council_base_url()
        if not base_url:
            return []
        closures: list[RoadClosureItem] = []
        seen_ids: set[str] = set()

        # 1. Local Council road closures
        try:
            council_roads = await self.async_fetch_json(f"{base_url}/dashboard/moretonRoadClosures")
            if isinstance(council_roads, dict):
                features = council_roads.get("features", [])
                for feat in features:
                    props = feat.get("properties", {})
                    geom = feat.get("geometry", {})
                    centroid = self.calculate_centroid(geom)
                    lat = centroid[0] if centroid else None
                    lon = centroid[1] if centroid else None
                    road_id = str(props.get("ID") or props.get("OBJECTID") or len(closures))
                    if road_id in seen_ids:
                        continue
                    seen_ids.add(road_id)
                    closures.append(
                        RoadClosureItem(
                            id=f"COUNCIL_{road_id}",
                            road=str(props.get("ROAD") or "Local Road"),
                            suburb=str(props.get("SUBURB") or ""),
                            status=str(props.get("STATUS") or "Closed"),
                            reason=props.get("REASON"),
                            description=props.get("DESCRIPTION"),
                            source="Local Council",
                            updated_at=self.parse_datetime(props.get("UPDATETIME")),
                            latitude=lat,
                            longitude=lon,
                        )
                    )
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("Error fetching local council road closures: %s", err)

        # 2. TMR Road Data (Department of Transport and Main Roads)
        try:
            tmr_url = f"{base_url}/dashboard/tmrRoadData"
            if tmr_url in self._payload_cache:
                tmr_data = self._payload_cache[tmr_url]
            else:
                tmr_data = await self.async_fetch_json(tmr_url)
            if isinstance(tmr_data, str):
                try:
                    tmr_data = json.loads(tmr_data)
                except Exception:  # noqa: BLE001
                    tmr_data = []
            if isinstance(tmr_data, list):
                for item in tmr_data:
                    props = item.get("properties", {})
                    geom = item.get("geometry", {})
                    centroid = self.calculate_centroid(geom)
                    lat = centroid[0] if centroid else None
                    lon = centroid[1] if centroid else None
                    raw_id = str(props.get("id") or item.get("id") or len(closures))
                    if raw_id in seen_ids:
                        continue
                    seen_ids.add(raw_id)
                    road_summary = props.get("road_summary", {}) if isinstance(props.get("road_summary"), dict) else {}
                    road_name = road_summary.get("road_name") or props.get("event_type", "Road Hazard")
                    suburb = road_summary.get("locality") or ""
                    impact = props.get("impact", {}) if isinstance(props.get("impact"), dict) else {}
                    subtype = (
                        impact.get("impact_subtype") or props.get("event_subtype") or props.get("event_type", "Hazard")
                    )
                    closures.append(
                        RoadClosureItem(
                            id=f"TMR_{raw_id}",
                            road=str(road_name),
                            suburb=str(suburb),
                            status=str(props.get("status", "Active")),
                            reason=str(props.get("event_due_to") or subtype),
                            description=props.get("description"),
                            advice=props.get("advice"),
                            source="Department of Transport and Main Roads",
                            updated_at=self.parse_datetime(props.get("last_updated")),
                            latitude=lat,
                            longitude=lon,
                        )
                    )
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("Error fetching TMR road data: %s", err)

        return closures

    async def async_fetch_weather_warnings(self) -> list[WeatherWarningItem]:
        """Fetch weather warnings summary from council BoM feed."""
        base_url = self._get_council_base_url()
        if not base_url:
            return []
        warnings: list[WeatherWarningItem] = []
        try:
            bom_url = f"{base_url}/dashboard/bom"
            if bom_url in self._payload_cache:
                bom_data = self._payload_cache[bom_url]
            else:
                bom_data = await self.async_fetch_json(bom_url)
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
            _LOGGER.debug("Error fetching weather warnings: %s", err)
        return warnings

    async def async_fetch_emergency_news(self) -> list[EmergencyNewsItem]:
        """Fetch emergency bulletins and media releases."""
        base_url = self._get_council_base_url()
        if not base_url:
            return []
        news_list: list[EmergencyNewsItem] = []
        try:
            bulletin_url = f"{base_url}/dashboard/imsBulletin"
            if bulletin_url in self._payload_cache:
                bulletin_data = self._payload_cache[bulletin_url]
            else:
                bulletin_data = await self.async_fetch_json(bulletin_url)
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
            _LOGGER.debug("Error fetching emergency news bulletins: %s", err)
        return news_list

    async def async_fetch_fire_danger(self) -> FireDangerRating | None:
        """Fetch AFDRS fire danger rating from council dashboard."""
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
            _LOGGER.debug("Error fetching Fire Danger Rating: %s", err)
        return None

    async def async_fetch_weather_telemetry(self) -> list[WeatherStationObservation]:
        """Fetch weather observations from local weather stations and Currtemp."""
        base_url = self._get_council_base_url()
        if not base_url:
            return []
        stations: list[WeatherStationObservation] = []
        try:
            data = await self.async_fetch_json(f"{base_url}/dashboard/getWeatherStationsData")
            if isinstance(data, list):
                for st in data:
                    st_id = str(st.get("id") or "")
                    st_name = str(st.get("name") or "Weather Station")
                    metrics: dict[str, float] = {}
                    for item in st.get("weatherData", []):
                        name = item.get("name")
                        val = item.get("currentValue")
                        if name and val is not None:
                            with contextlib.suppress(ValueError, TypeError):
                                metrics[name] = float(val)
                    stations.append(
                        WeatherStationObservation(
                            station_id=st_id,
                            station_name=st_name,
                            temperature=metrics.get("TenMin - AirTC"),
                            relative_humidity=metrics.get("TenMin - RH"),
                            pressure_hpa=metrics.get("TenMin - BP hPa"),
                            wind_direction=metrics.get("Hourly - WindDir-Avg-Vect"),
                            wind_speed_avg=metrics.get("Hourly - ws-kph-Avg"),
                            wind_speed_max=metrics.get("Hourly - ws-kph-Max"),
                            solar_radiation=metrics.get("TenMin - SlrW"),
                        )
                    )
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("Error fetching weather stations telemetry: %s", err)

        if not stations:
            try:
                curr = await self.async_fetch_json(f"{base_url}/dashboard/Currtemp")
                if isinstance(curr, dict) and curr.get("air_temp") is not None:
                    stations.append(
                        WeatherStationObservation(
                            station_id="currtemp",
                            station_name="Current Conditions",
                            temperature=float(curr["air_temp"]),
                            apparent_temperature=float(curr.get("apparent_t", curr["air_temp"])),
                        )
                    )
            except Exception as err:  # noqa: BLE001
                _LOGGER.debug("Error fetching Currtemp fallback: %s", err)

        return stations

    async def async_fetch_air_quality(self) -> list[AirQualityStationData]:
        """Fetch air quality observations from monitoring stations."""
        base_url = self._get_council_base_url()
        if not base_url:
            return []
        stations: list[AirQualityStationData] = []
        try:
            aq_data = await self.async_fetch_json(f"{base_url}/dashboard/airQuality?stationIds=burp,pcer,dcb,kipp,petr")
            if isinstance(aq_data, dict):
                station_list = aq_data.get("AirQualityStationDataList", [])
                for item in station_list:
                    overall = item.get("PM2_5_Rating") or item.get("PM10_Rating") or "Good"
                    stations.append(
                        AirQualityStationData(
                            station_id=str(item.get("station_id") or ""),
                            station_name=str(item.get("station_name") or "Air Station"),
                            pm2_5_measurement=item.get("PM2_5_Measurement"),
                            pm2_5_rating=item.get("PM2_5_Rating"),
                            pm2_5_running_average=item.get("PM2_5_Running_Average"),
                            pm10_measurement=item.get("PM10_Measurement"),
                            pm10_rating=item.get("PM10_Rating"),
                            pm10_running_average=item.get("PM10_Running_Average"),
                            no2_measurement=item.get("NO2_Measurement"),
                            no2_rating=item.get("NO2_Rating"),
                            o3_measurement=item.get("O3_Measurement"),
                            o3_rating=item.get("O3_Rating"),
                            overall_rating=str(overall),
                        )
                    )
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("Error fetching air quality: %s", err)
        return stations

    async def async_fetch_relief_facilities(self) -> list[ReliefFacilityItem]:
        """Fetch sandbag stations, evacuation centres, and places of refuge."""
        base_url = self._get_council_base_url()
        if not base_url:
            return []
        facilities: list[ReliefFacilityItem] = []

        # Sandbags
        try:
            sandbags = await self.async_fetch_json(f"{base_url}/dashboard/sandbagStations")
            if isinstance(sandbags, dict):
                for feat in sandbags.get("features", []):
                    props = feat.get("properties", {})
                    centroid = self.calculate_centroid(feat.get("geometry", {}))
                    facilities.append(
                        ReliefFacilityItem(
                            id=f"sandbag_{props.get('OBJECTID') or stable_id('qld_relief', props.get('NAME'), centroid)}",
                            facility_type="sandbag_station",
                            name=str(props.get("NAME") or "Sandbag Station"),
                            suburb=str(props.get("SUBURB") or ""),
                            address=str(props.get("ADDRESS") or ""),
                            status="Open",
                            latitude=centroid[0] if centroid else None,
                            longitude=centroid[1] if centroid else None,
                        )
                    )
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("Error fetching sandbag stations: %s", err)

        # Evacuation Centres
        try:
            evacs = await self.async_fetch_json(f"{base_url}/dashboard/moretonEvacs")
            if isinstance(evacs, dict):
                for feat in evacs.get("features", []):
                    props = feat.get("properties", {})
                    centroid = self.calculate_centroid(feat.get("geometry", {}))
                    facilities.append(
                        ReliefFacilityItem(
                            id=f"evac_{props.get('OBJECTID') or stable_id('qld_relief', props.get('NAME'), centroid)}",
                            facility_type="evacuation_centre",
                            name=str(props.get("NAME") or "Evacuation Centre"),
                            suburb=str(props.get("SUBURB") or ""),
                            address=str(props.get("ADDRESS") or ""),
                            status="Open",
                            latitude=centroid[0] if centroid else None,
                            longitude=centroid[1] if centroid else None,
                        )
                    )
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("Error fetching evacuation centres: %s", err)

        return facilities

    async def async_fetch_cameras(self) -> list[DisasterCameraItem]:
        """Fetch flood and traffic webcams."""
        base_url = self._get_council_base_url()
        if not base_url:
            return []
        return [
            DisasterCameraItem(
                id="qld_goodna_ipswich_mwy",
                name="Goodna - Ipswich Mwy East",
                image_url="http://131940.qld.gov.au/img/WebCamImages/Metropolitan/Goodna_Ipswich_Mwy_East.jpg",
                suburb="Goodna",
                latitude=-27.6083,
                longitude=152.8942,
            ),
            DisasterCameraItem(
                id="qld_dinmore_ipswich_mwy",
                name="Dinmore - Ipswich Mwy East",
                image_url="http://131940.qld.gov.au/img/WebCamImages/Metropolitan/Dinmore_Ipswich_Mwy_east.jpg",
                suburb="Dinmore",
                latitude=-27.5956,
                longitude=152.8365,
            ),
            DisasterCameraItem(
                id="qld_metro_1218",
                name="Metropolitan Camera 1218",
                image_url="http://131940.qld.gov.au/img/WebCamImages/Metropolitan/MRMETRO-1218.jpg",
                suburb="Brisbane / Moreton",
                latitude=-27.3500,
                longitude=153.0000,
            ),
            DisasterCameraItem(
                id="qld_bruce_hwy_caboolture",
                name="Bruce Highway - Caboolture",
                image_url="http://131940.qld.gov.au/img/WebCamImages/NorthCoast/MRNC-0131.jpg",
                suburb="Caboolture",
                latitude=-27.0850,
                longitude=152.9550,
            ),
        ]

    async def async_fetch_nearby_councils(self) -> list[dict[str, str]]:
        """Fetch nearby council disaster dashboard links."""
        base_url = self._get_council_base_url()
        if not base_url:
            return []
        return [
            {"name": "Sunshine Coast Regional Council", "url": "https://disasterhub.sunshinecoast.qld.gov.au"},
            {"name": "City of Gold Coast", "url": "https://dashboard.cityofgoldcoast.com.au"},
            {"name": "Brisbane City Council", "url": "https://disaster.brisbane.qld.gov.au"},
            {"name": "Somerset Regional Council", "url": "http://disaster.somerset.qld.gov.au"},
            {"name": "Noosa Shire Council", "url": "https://disaster.noosa.qld.gov.au"},
        ]
