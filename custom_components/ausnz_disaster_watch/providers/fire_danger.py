"""Fire danger outlook and total fire bans for any Australian location; NZ fire season (#28).

Australia: the configured location is matched to its BoM fire weather district with the
bundled ``IDM00007`` polygons. The district's 4-day fire danger forecast comes from the
Bureau of Meteorology's per-state fire danger XML product, which dates each day in the
state's local time, so "today" is never yesterday's or tomorrow's forecast. Total fire
bans come from the agency that declares them (see ``fire_bans``). Queensland and the
Northern Territory publish no total fire ban feed; TasALERT's ban feed needs permission,
so Tasmanian bans are not read.

New Zealand: Fire and Emergency NZ's fire season zone and Section 52 prohibitions at the
configured location (ArcGIS point queries).

Fire danger is issued about twice a day, so sources are polled at most every 30 minutes,
independent of the hazard poll interval. A failed poll keeps the last good outlook (its
days are dated, so it never shows an old day as today).
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import UTC, date, datetime, timedelta
import logging
from typing import Any

import defusedxml.ElementTree as ET

from custom_components.ausnz_disaster_watch.const import STATE_NZ, STATE_TIMEZONES
from custom_components.ausnz_disaster_watch.fire_districts import FIRE_DISTRICTS, district_name, resolve_district
from custom_components.ausnz_disaster_watch.models import (
    CanonicalHazard,
    FireDangerDay,
    FireDangerOutlook,
    FireSeasonStatus,
)
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from . import fire_bans
from .base import MALFORMED_ITEM_ERRORS, BaseHazardProvider, ProviderUnavailableError
from .sources import DataSource, sources_for_fire

_LOGGER = logging.getLogger(__name__)

FIRE_REFRESH_INTERVAL = timedelta(minutes=30)
# Persisted outlook, so a restart after the afternoon issue keeps today's rating (#89)
FIRE_STORAGE_VERSION = 1
FIRE_STORAGE_KEY = "ausnz_disaster_watch.fire_outlook.{entry_id}"
FIRE_RETRY_INTERVAL = timedelta(minutes=5)

BOM_FIRE_DANGER_URL = "https://www.bom.gov.au/fwo/{product}.xml"
BOM_FIRE_DANGER_SOURCE = "Bureau of Meteorology"

# BoM fire danger forecast product per district AAC prefix. ACT (NSW_FW008) is in the NSW product.
BOM_FIRE_DANGER_PRODUCTS: dict[str, str] = {
    "NSW": "IDN10016",
    "VIC": "IDV18555",
    "QLD": "IDQ13016",
    "SA": "IDS10070",
    "WA": "IDW15100",
    "TAS": "IDT13151",
    "NT": "IDD10731",
}

ACT_DISTRICT = "NSW_FW008"

# ABS approximation of local government areas, for Emergency WA's per-LGA total fire bans
ABS_LGA_QUERY_URL = (
    "https://geo.abs.gov.au/arcgis/rest/services/ASGS2021/LGA/MapServer/0/query"
    "?geometry={lon},{lat}&geometryType=esriGeometryPoint&inSR=4326"
    "&spatialRel=esriSpatialRelIntersects&outFields=lga_name_2021&returnGeometry=false&f=json"
)

NZ_FIRE_SEASON_URL = (
    "https://utility.arcgis.com/usrsvcs/servers/b381ba9bdd4046c2b71a6b1a1e39da78/rest/services/FENZ/MapServer/27/query"
    "?geometry={lon},{lat}&geometryType=esriGeometryPoint&inSR=4326&spatialRel=esriSpatialRelIntersects"
    "&outFields=SEASON,Name,District,LAST_UPDATED&returnGeometry=false&f=json"
)
NZ_SECTION_52_URL = (
    "https://services1.arcgis.com/dcVyucRsXCQAi3GL/arcgis/rest/services/Section_52_Localities_v2_view/FeatureServer/0/query"
    "?geometry={lon},{lat}&geometryType=esriGeometryPoint&inSR=4326&spatialRel=esriSpatialRelIntersects"
    "&outFields=*&returnGeometry=false&f=json"
)
NZ_SEASONS = ("open", "restricted", "prohibited")
# Section 52 activity flags: 1 = allowed, 0 = prohibited
NZ_SECTION_52_ACTIVITIES: dict[str, str] = {
    "Bonfire": "bonfires",
    "Campfire": "campfires",
    "Cultural_Cooking_Fire": "cultural_cooking_fires",
    "Pizza_Ovens": "pizza_ovens",
    "Fire_Pits": "fire_pits",
    "Gas_BBQ": "gas_bbqs",
    "Charcoal_BBQ": "charcoal_bbqs",
    "Incinerators": "incinerators",
    "Fire_Land_Management": "land_management_fires",
    "Hot_Works": "hot_works",
    "Machinery": "machinery",
    "Vehicles": "vehicles",
    "Fireworks": "fireworks",
}

# AFDRS rating display names, keyed by normalised feed text
_RATINGS = {
    "norating": "No Rating",
    "none": "No Rating",
    "moderate": "Moderate",
    "high": "High",
    "extreme": "Extreme",
    "catastrophic": "Catastrophic",
}

type FireDistrict = tuple[str, str]  # (AAC, name)


def normalise_rating(value: str | None) -> str | None:
    """Return the AFDRS display name for a feed rating (``EXTREME`` -> ``Extreme``)."""
    if value is None or not value.strip():
        return None
    return _RATINGS.get(fire_bans.normalise_name(value), value.strip().title())


def district_time_zone(aac: str) -> str:
    """Return the IANA time zone a district's forecast days are dated in."""
    return STATE_TIMEZONES.get(aac.split("_", 1)[0], "Australia/Sydney")


def local_today(time_zone: str) -> date:
    """Return today's date in a jurisdiction's time zone."""
    zone = dt_util.get_time_zone(time_zone) or UTC
    return dt_util.now(zone).date()


def parse_bom_fire_danger(xml_text: str, aac: str, name: str) -> FireDangerOutlook | None:
    """Parse a BoM fire danger forecast product (service WSF) for one district.

    Each ``fire-district`` area has up to four ``forecast-period`` elements dated in local
    time with ``fire_danger`` text and a ``fire_behaviour_index``. Returns None when the
    product does not list the district.
    """
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as err:
        raise ProviderUnavailableError(f"BoM fire danger forecast is not valid XML: {err}") from err
    if root.tag != "product" or root.find("forecast") is None:
        raise ProviderUnavailableError(f"BoM fire danger forecast returned an unexpected document <{root.tag}>")

    area = next((a for a in root.iterfind("forecast/area") if a.get("aac") == aac), None)
    if area is None:
        return None
    days: list[FireDangerDay] = []
    for period in area.iterfind("forecast-period"):
        try:
            day = datetime.fromisoformat(period.get("start-time-local") or "").date()
            fbi_text = period.findtext("element[@type='fire_behaviour_index']")
            days.append(
                FireDangerDay(
                    date=day,
                    rating=normalise_rating(period.findtext("text[@type='fire_danger']")),
                    fire_behaviour_index=int(fbi_text) if fbi_text and fbi_text.strip() else None,
                )
            )
        except MALFORMED_ITEM_ERRORS as err:
            _LOGGER.debug("Skipping malformed BoM fire danger period for %s: %s", aac, err)
    issued = BaseHazardProvider.parse_datetime(root.findtext("amoc/issue-time-utc"), "UTC")
    return FireDangerOutlook(
        district_number=aac,
        district_name=area.get("description") or name,
        time_zone=district_time_zone(aac),
        issued_at=issued,
        source=BOM_FIRE_DANGER_SOURCE,
        days=sorted(days, key=lambda d: d.date),
    )


def merge_outlooks(previous: FireDangerOutlook | None, current: FireDangerOutlook | None) -> FireDangerOutlook | None:
    """Keep today's forecast from the previous issue when the new issue starts tomorrow.

    Afternoon issues (e.g. QLD's 4 pm product) cover tomorrow onwards only. Without this,
    the rating would go unknown every evening until midnight.
    """
    if previous is None or current is None or previous.district_number != current.district_number:
        return current
    today = local_today(current.time_zone)
    covered = {day.date for day in current.days}
    carried = [day for day in previous.days if day.date >= today and day.date not in covered]
    if carried:
        current.days = sorted([*carried, *current.days], key=lambda d: d.date)
    return current


# Marks the Store's content as not yet known (distinct from None: nothing stored)
_UNKNOWN = object()


type AgencyReport = tuple[dict[date, bool | None], dict[date, str | None]]


def fill_from_agency(outlook: FireDangerOutlook, ratings: dict[date, str | None], label: str) -> None:
    """Use the agency's rating for today when the BoM forecast has no day for today (#89).

    BoM's afternoon issue starts tomorrow. With no earlier issue known (for example after a
    restart), the agency that publishes today's rating fills that one day; BoM's own days
    always win and the agency never extends the outlook beyond them.
    """
    today = local_today(outlook.time_zone)
    if outlook.day(today) is not None or (rating := normalise_rating(ratings.get(today))) is None:
        return
    outlook.days = sorted([*outlook.days, FireDangerDay(date=today, rating=rating, source=label)], key=lambda d: d.date)


def outlook_to_dict(outlook: FireDangerOutlook) -> dict[str, Any]:
    """Return a JSON-safe dict of an outlook for the Store."""
    return {
        "district_number": outlook.district_number,
        "district_name": outlook.district_name,
        "time_zone": outlook.time_zone,
        "issued_at": outlook.issued_at.isoformat() if outlook.issued_at else None,
        "source": outlook.source,
        "total_fire_ban_source": outlook.total_fire_ban_source,
        "days": [
            {
                "date": day.date.isoformat(),
                "rating": day.rating,
                "fire_behaviour_index": day.fire_behaviour_index,
                "total_fire_ban": day.total_fire_ban,
                "source": day.source,
            }
            for day in outlook.days
        ],
    }


def outlook_from_dict(data: Any) -> FireDangerOutlook | None:
    """Rebuild a stored outlook; None when the data is missing or not a stored outlook."""
    if not isinstance(data, dict):
        return None
    try:
        issued = data.get("issued_at")
        return FireDangerOutlook(
            district_number=str(data["district_number"]),
            district_name=str(data["district_name"]),
            time_zone=str(data["time_zone"]),
            issued_at=datetime.fromisoformat(issued) if issued else None,
            source=str(data["source"]),
            total_fire_ban_source=data.get("total_fire_ban_source"),
            days=[
                FireDangerDay(
                    date=date.fromisoformat(day["date"]),
                    rating=day.get("rating"),
                    fire_behaviour_index=day.get("fire_behaviour_index"),
                    total_fire_ban=day.get("total_fire_ban"),
                    source=day.get("source"),
                )
                for day in data["days"]
            ],
        )
    except MALFORMED_ITEM_ERRORS as err:
        _LOGGER.debug("Ignoring a malformed stored fire danger outlook: %s", err)
        return None


async def async_remove_stored_outlook(hass: Any, entry_id: str) -> None:
    """Delete an entry's persisted outlook when the entry is removed."""
    await Store(hass, FIRE_STORAGE_VERSION, FIRE_STORAGE_KEY.format(entry_id=entry_id)).async_remove()


def parse_nz_fire_season(season_payload: Any, section_52_payload: Any) -> FireSeasonStatus:
    """Parse the FENZ fire season zone and Section 52 point query results."""
    features = season_payload.get("features") if isinstance(season_payload, dict) else None
    if not isinstance(features, list):
        raise ProviderUnavailableError("FENZ fire season query returned an unexpected payload")
    status = FireSeasonStatus()
    attributes = next((f.get("attributes") for f in features if isinstance(f, dict)), None)
    if isinstance(attributes, dict):
        season = str(attributes.get("SEASON") or "").strip().lower()
        status.season = season if season in NZ_SEASONS else None
        status.zone = attributes.get("Name")
        status.district = attributes.get("District")
        updated = attributes.get("LAST_UPDATED")
        if isinstance(updated, (int, float)):
            status.last_updated = datetime.fromtimestamp(updated / 1000, tz=UTC)

    s52 = section_52_payload.get("features") if isinstance(section_52_payload, dict) else None
    if isinstance(s52, list):
        active = [
            f["attributes"]
            for f in s52
            if isinstance(f, dict) and isinstance(f.get("attributes"), dict) and f["attributes"].get("Section52") == 1
        ]
        status.section_52 = bool(active)
        if active:
            status.section_52_comment = active[0].get("Comment")
            status.prohibited_activities = sorted(
                {label for zone in active for field, label in NZ_SECTION_52_ACTIVITIES.items() if zone.get(field) == 0}
            )
    return status


class FireDangerService(BaseHazardProvider):
    """Fetches the fire danger outlook (AU) or fire season (NZ) for the configured location.

    It reuses the provider HTTP helpers but is not a hazard provider: the coordinator owns
    it separately and it publishes no hazards.
    """

    def __init__(self, *args: Any, entry_id: str | None = None, **kwargs: Any) -> None:
        """Initialise with empty state; nothing is fetched until the first update.

        With ``entry_id`` the last outlook is kept in a Home Assistant Store, so a restart
        after BoM's afternoon issue (which starts tomorrow) still has today's rating (#89).
        """
        super().__init__(*args, **kwargs)
        self.outlook: FireDangerOutlook | None = None
        self._store: Store[dict[str, Any]] | None = (
            Store(self.hass, FIRE_STORAGE_VERSION, FIRE_STORAGE_KEY.format(entry_id=entry_id)) if entry_id else None
        )
        self._restored = False
        # What the Store holds: _UNKNOWN until it is read or written, None once removed
        self._saved: dict[str, Any] | None | object = _UNKNOWN
        self.season: FireSeasonStatus | None = None
        self._next_refresh: datetime | None = None
        # ((lat, lon), district) and ((lat, lon), LGA name) for the last resolved location
        self._district: tuple[tuple[float, float], FireDistrict | None] | None = None
        self._lga: tuple[tuple[float, float], str] | None = None

    def set_location(self, latitude: float, longitude: float) -> None:
        """Follow the monitoring point; a move refreshes on the next update instead of in 30 minutes."""
        if self._location() != (latitude, longitude):
            self._next_refresh = None
        super().set_location(latitude, longitude)

    @property
    def state_code(self) -> str:
        """Return the configured jurisdiction."""
        return str(self.config.get("state", "")).upper()

    async def async_fetch_hazards(self) -> list[CanonicalHazard]:
        """Publish no hazards (fire danger is not a hazard)."""
        return []

    @property
    def data_sources(self) -> tuple[DataSource, ...]:
        """Return the sources for the location's district (the configured state until it is resolved)."""
        district = self._district[1] if self._district else None
        if district is None:
            return sources_for_fire(self.state_code)
        aac = district[0]
        return sources_for_fire("ACT" if aac == ACT_DISTRICT else aac.split("_", 1)[0])

    def _location(self) -> tuple[float, float] | None:
        try:
            return float(self.config["latitude"]), float(self.config["longitude"])
        except (KeyError, TypeError, ValueError):
            return None

    async def async_update(self) -> None:
        """Refresh the outlook or fire season if due. Never raises: fire data is best effort."""
        now = dt_util.utcnow()
        if self._next_refresh is not None and now < self._next_refresh:
            return
        try:
            if self.state_code == STATE_NZ:
                self.season = await self._async_fetch_season()
            else:
                await self._async_restore()
                self.outlook = await self._async_fetch_outlook()
                await self._async_persist()
        except Exception as err:  # noqa: BLE001 - a fire source must never break hazard updates
            _LOGGER.debug("Fire danger update failed; keeping the last good data: %s", err)
            self._next_refresh = now + FIRE_RETRY_INTERVAL
            return
        self._next_refresh = now + FIRE_REFRESH_INTERVAL

    async def _async_restore(self) -> None:
        """Load the persisted outlook once, before the first fetch (#89)."""
        if self._restored or self._store is None:
            return
        self._restored = True
        try:
            stored = await self._store.async_load()
        except Exception as err:  # noqa: BLE001 - a damaged store must not block fire data
            _LOGGER.debug("Ignoring the stored fire danger outlook: %s", err)
            return
        self._saved = stored if isinstance(stored, dict) else None
        if self.outlook is None and (restored := outlook_from_dict(stored)) is not None:
            self.outlook = restored

    async def _async_persist(self) -> None:
        """Save the outlook when it changed, or drop the stored one when there is none.

        The outlook is refreshed every 30 minutes but changes about twice a day, so an
        unchanged outlook is not written again (fewer writes on SD-card installs).
        """
        if self._store is None:
            return
        if self.outlook is None:
            if self._saved is not None:
                await self._store.async_remove()
                self._saved = None
            return
        data = outlook_to_dict(self.outlook)
        if data != self._saved:
            await self._store.async_save(data)
            self._saved = data

    async def _async_district(self, location: tuple[float, float]) -> FireDistrict | None:
        """Resolve (once per location, in an executor) the location's fire weather district."""
        if self._district is None or self._district[0] != location:
            aac = await self.hass.async_add_executor_job(resolve_district, FIRE_DISTRICTS, *location)
            district = None
            if aac is not None:
                district = (aac, await self.hass.async_add_executor_job(district_name, FIRE_DISTRICTS, aac))
            self._district = (location, district)
        return self._district[1]

    async def _async_fetch_outlook(self) -> FireDangerOutlook | None:
        location = self._location()
        if location is None:
            return None
        district = await self._async_district(location)
        if district is None:
            return None
        aac, name = district
        product = BOM_FIRE_DANGER_PRODUCTS.get(aac.split("_", 1)[0])
        if product is None:
            return None
        text = await self.async_fetch_feed_text(BOM_FIRE_DANGER_URL.format(product=product), "BoM fire danger")
        outlook = parse_bom_fire_danger(text, aac, name)
        if outlook is None:
            return None
        # An afternoon issue starts tomorrow: keep today from the earlier (possibly persisted) issue
        outlook = merge_outlooks(self.outlook, outlook) or outlook

        agency = self._agency_source(outlook, location)
        if agency is not None:
            label, fetch = agency
            try:
                bans, ratings = await fetch()
            except (ProviderUnavailableError, *MALFORMED_ITEM_ERRORS) as err:
                # Ratings are still useful without bans; unknown bans stay None, never False
                _LOGGER.debug("Total fire ban source %s failed: %s", label, err)
            else:
                fill_from_agency(outlook, ratings, label)
                outlook.total_fire_ban_source = label
                for day in outlook.days:
                    day.total_fire_ban = bans.get(day.date)
        return outlook

    def _agency_source(
        self, outlook: FireDangerOutlook, location: tuple[float, float]
    ) -> tuple[str, Callable[[], Awaitable[AgencyReport]]] | None:
        """Return (source name, fetch) for the agency that declares bans in this district.

        The fetch returns that agency's bans and its own ratings per day. The ratings fill days
        the BoM forecast does not cover, such as today after BoM's afternoon issue (#89).
        """
        aac = outlook.district_number
        prefix = aac.split("_", 1)[0]
        tz = dt_util.get_time_zone(outlook.time_zone) or UTC
        today = local_today(outlook.time_zone)

        async def _xml(url: str, label: str) -> Any:
            text = await self.async_fetch_feed_text(url, label)
            try:
                return ET.fromstring(text)
            except ET.ParseError as err:
                raise ProviderUnavailableError(f"{label} is not valid XML: {err}") from err

        if aac == ACT_DISTRICT:

            async def _act() -> AgencyReport:
                root = await _xml(fire_bans.ACT_ESA_FDR_URL, "ACT ESA fire danger")
                return (
                    fire_bans.parse_fdr_toban_xml(root, aac, today, tz),
                    fire_bans.parse_fdr_toban_ratings(root, aac, today, tz),
                )

            return "ACT Emergency Services Agency", _act
        if prefix == "NSW":

            async def _nsw() -> AgencyReport:
                try:
                    payload = await self.async_fetch_feed_json(fire_bans.NSW_RFS_FDR_URL, "NSW RFS fire danger")
                    return (
                        fire_bans.parse_nsw_rfs_v2(payload, aac, today),
                        fire_bans.parse_nsw_rfs_v2_ratings(payload, aac, today),
                    )
                except ProviderUnavailableError as err:
                    _LOGGER.debug("NSW RFS 4-day feed failed, using fdrToban.xml: %s", err)
                root = await _xml(fire_bans.NSW_RFS_TOBAN_URL, "NSW RFS fire bans")
                return (
                    fire_bans.parse_fdr_toban_xml(root, aac, today, tz),
                    fire_bans.parse_fdr_toban_ratings(root, aac, today, tz),
                )

            return "NSW Rural Fire Service", _nsw
        if prefix == "VIC":

            async def _vic() -> AgencyReport:
                root = await _xml(fire_bans.VIC_CFA_TFB_URL, "CFA fire bans")
                return (
                    fire_bans.parse_vic_cfa_rss(root, outlook.district_name),
                    fire_bans.parse_vic_cfa_ratings(root, outlook.district_name),
                )

            return "Country Fire Authority", _vic
        if prefix == "SA":

            async def _sa() -> AgencyReport:
                root = await _xml(fire_bans.SA_CFS_FDR_URL, "SA CFS fire bans")
                return (
                    fire_bans.parse_sa_cfs_xml(root, outlook.district_name),
                    fire_bans.parse_sa_cfs_ratings(root, outlook.district_name),
                )

            return "SA Country Fire Service", _sa
        if prefix == "WA":

            async def _wa() -> AgencyReport:
                ratings: dict[date, str | None] = {}
                # Emergency WA publishes ratings in a separate feed: read it only when BoM lacks today
                if outlook.day(today) is None:
                    try:
                        fdr = await self.async_fetch_feed_json(fire_bans.WA_FDR_URL, "Emergency WA fire danger")
                        ratings = fire_bans.parse_wa_fdr_ratings(fdr, aac, tz)
                    except ProviderUnavailableError as err:
                        _LOGGER.debug("Emergency WA fire danger ratings failed: %s", err)
                lga = await self._async_lga(location)
                payload = await self.async_fetch_feed_json(fire_bans.WA_TFB_URL, "Emergency WA total fire bans")
                days = sorted({d.date for d in outlook.days} | ({today} if today in ratings else set()))
                return fire_bans.parse_wa_total_fire_bans(payload, lga, days), ratings

            return "Department of Fire and Emergency Services WA", _wa
        return None

    async def _async_lga(self, location: tuple[float, float]) -> str:
        """Return the local government area at the location (ABS boundaries, cached per location)."""
        if self._lga is None or self._lga[0] != location:
            lat, lon = location
            payload = await self.async_fetch_feed_json(ABS_LGA_QUERY_URL.format(lat=lat, lon=lon), "ABS LGA lookup")
            features = payload.get("features") if isinstance(payload, dict) else None
            name = None
            if isinstance(features, list) and features and isinstance(features[0], dict):
                name = (features[0].get("attributes") or {}).get("lga_name_2021")
            if not name:
                raise ProviderUnavailableError("No local government area found for the location")
            self._lga = (location, str(name))
        return self._lga[1]

    async def _async_fetch_season(self) -> FireSeasonStatus | None:
        location = self._location()
        if location is None:
            return None
        lat, lon = location
        season = await self.async_fetch_feed_json(NZ_FIRE_SEASON_URL.format(lat=lat, lon=lon), "FENZ fire season")
        try:
            section_52 = await self.async_fetch_feed_json(
                NZ_SECTION_52_URL.format(lat=lat, lon=lon), "FENZ Section 52 prohibitions"
            )
        except ProviderUnavailableError as err:
            _LOGGER.debug("FENZ Section 52 query failed: %s", err)
            section_52 = None
        return parse_nz_fire_season(season, section_52)
