"""Opt-in national and regional feeds: tsunami, satellite hotspots, heatwave, UV, air quality, GDACS (#37).

The provider contributes no hazards. Each feed has its own option (all off by default), its
own refresh interval and its own last-good cache: a failed refresh keeps the previous value
for a bounded time and then reports ``None`` ("undetermined"), which makes the matching
entity unavailable instead of showing an all-clear. Tsunami and UV observations are checked
on every poll; the slower products are refreshed less often to stay polite to the sources.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any, ClassVar

from custom_components.ausnz_disaster_watch.const import (
    CONF_ENABLE_AIR_QUALITY,
    CONF_ENABLE_HEATWAVE,
    CONF_ENABLE_REGIONAL_ALERTS,
    CONF_ENABLE_SATELLITE_HOTSPOTS,
    CONF_ENABLE_TSUNAMI,
    CONF_ENABLE_UV,
    DEFAULT_RADIUS,
    LAST_GOOD_MAX_AGE,
    STATE_ACT,
    STATE_NSW,
    STATE_NZ,
    STATE_QLD,
)
from custom_components.ausnz_disaster_watch.models import (
    AirQualityStationData,
    CanonicalHazard,
    HeatwaveStatus,
    RegionalAlertItem,
    SatelliteHotspots,
    TsunamiStatus,
    UVObservation,
)
from homeassistant.util import dt as dt_util

from . import air_quality, gdacs, heatwave, hotspots, tsunami, uv
from .base import BaseHazardProvider, FeedCache, ProviderUnavailableError
from .bom_ftp import async_fetch_bom_products
from .cap import CapAlert, CapDocumentCache

HOTSPOTS_TTL = timedelta(minutes=30)
HEATWAVE_TTL = timedelta(minutes=60)
UV_FORECAST_TTL = timedelta(minutes=60)
GDACS_TTL = timedelta(minutes=15)
AIR_QUALITY_TTL = timedelta(minutes=30)
NSW_SITES_TTL = timedelta(hours=24)
# Feeds checked every poll keep their last good value for the same time as hazards (#16)
EVERY_POLL = timedelta(0)


class NationalHazardProvider(BaseHazardProvider):
    """National and regional feeds for one config entry; contributes no hazards."""

    # Excluded from the hazard fetch, so its success never masks an outage of the real feeds
    provides_hazards: ClassVar[bool] = False

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialise one cache per feed."""
        super().__init__(*args, **kwargs)
        self._tsunami = FeedCache[TsunamiStatus]("Tsunami status", EVERY_POLL, LAST_GOOD_MAX_AGE)
        self._hotspots = FeedCache[SatelliteHotspots]("DEA hotspots", HOTSPOTS_TTL, 4 * HOTSPOTS_TTL)
        self._heatwave = FeedCache[HeatwaveStatus]("BoM heatwave", HEATWAVE_TTL, 3 * HEATWAVE_TTL)
        self._uv = FeedCache[UVObservation]("ARPANSA UV", EVERY_POLL, LAST_GOOD_MAX_AGE)
        self._uv_forecast = FeedCache[dict[str, bytes]]("BoM UV forecast", UV_FORECAST_TTL, 3 * UV_FORECAST_TTL)
        self._gdacs = FeedCache[list[RegionalAlertItem]]("GDACS", GDACS_TTL, 4 * GDACS_TTL)
        self._air_quality = FeedCache[list[AirQualityStationData]]("Air quality", AIR_QUALITY_TTL, 4 * AIR_QUALITY_TTL)
        self._nsw_sites = FeedCache[list[Any]]("NSW air quality sites", NSW_SITES_TTL, 7 * NSW_SITES_TTL)
        self._ptwc_documents = CapDocumentCache("PTWC CAP document")

    @property
    def state_code(self) -> str:
        """Return the configured jurisdiction."""
        return str(self.config.get("state", STATE_QLD)).upper()

    @property
    def _is_nz(self) -> bool:
        return self.state_code == STATE_NZ

    @property
    def _location(self) -> tuple[float, float] | None:
        try:
            return float(self.config["latitude"]), float(self.config["longitude"])
        except (KeyError, TypeError, ValueError):
            return None

    @property
    def _radius_km(self) -> float:
        return float(self.config.get("radius") or DEFAULT_RADIUS)

    def _enabled(self, option: str, *, au_only: bool = False) -> bool:
        return bool(self.config.get(option, False)) and not (au_only and self._is_nz)

    async def async_fetch_hazards(self) -> list[CanonicalHazard]:
        """National feeds are not hazards; see the module docstring."""
        return []

    # Tsunami

    async def async_fetch_tsunami_status(self) -> TsunamiStatus | None:
        """Return the JATWC status (Australia) or PTWC guidance (New Zealand)."""
        if not self._enabled(CONF_ENABLE_TSUNAMI):
            return None
        return await self._tsunami.async_get(self._async_ptwc if self._is_nz else self._async_jatwc)

    async def _async_jatwc(self) -> TsunamiStatus:
        files = await async_fetch_bom_products(self.hass, (tsunami.JATWC_FTP_PATTERN,), tsunami.is_jatwc_cap_file)
        return tsunami.jatwc_status(files, self.state_code, dt_util.utcnow())

    async def _async_ptwc(self) -> TsunamiStatus:
        feed = await self.async_fetch_feed_text(tsunami.PTWC_ATOM_URL, "PTWC tsunami feed")
        links = tsunami.ptwc_cap_links(feed)
        self._ptwc_documents.prune(set(links))
        loaded = await self._ptwc_documents.async_load(
            lambda url: self.async_fetch_feed_text(url, "PTWC CAP document"), [(url, url, url) for url in links]
        )
        alerts: list[CapAlert] = [alert for _, alert in loaded]
        return tsunami.ptwc_status(alerts, dt_util.utcnow())

    # Satellite hotspots

    async def async_fetch_satellite_hotspots(self) -> SatelliteHotspots | None:
        """Return DEA hotspots within the monitoring radius."""
        if not self._enabled(CONF_ENABLE_SATELLITE_HOTSPOTS, au_only=True) or (location := self._location) is None:
            return None
        radius = self._radius_km

        async def fetch() -> SatelliteHotspots:
            url = hotspots.hotspot_query_url(location[0], location[1], radius)
            payload = await self.async_fetch_feed_json(url, "DEA hotspots")
            return hotspots.parse_hotspots(payload, location[0], location[1], radius)

        return await self._hotspots.async_get(fetch)

    # Heatwave

    async def async_fetch_heatwave(self) -> HeatwaveStatus | None:
        """Return the heatwave warning severity for the configured state."""
        product = heatwave.HEATWAVE_PRODUCTS.get(self.state_code)
        if not self._enabled(CONF_ENABLE_HEATWAVE, au_only=True) or product is None:
            return None
        name = heatwave.heatwave_cap_file(product)

        async def fetch() -> HeatwaveStatus:
            files = await async_fetch_bom_products(self.hass, (name,), lambda listed: listed == name)
            return heatwave.heatwave_status(product, files.get(name), dt_util.utcnow())

        return await self._heatwave.async_get(fetch)

    # UV

    async def async_fetch_uv(self) -> UVObservation | None:
        """Return the UV index at the nearest ARPANSA station with the BoM forecast."""
        if not self._enabled(CONF_ENABLE_UV, au_only=True) or (location := self._location) is None:
            return None

        async def fetch() -> UVObservation:
            text = await self.async_fetch_feed_text(uv.ARPANSA_UV_URL, "ARPANSA UV feed")
            nearest = uv.nearest_reading(uv.parse_arpansa(text), *location)
            if nearest is None:
                raise ProviderUnavailableError("ARPANSA UV feed has no current station reading")
            reading, distance = nearest
            return uv.uv_observation(reading, distance, await self._async_uv_forecast(reading.station))

        return await self._uv.async_get(fetch)

    async def _async_uv_forecast(self, station: str) -> tuple[str, int | None] | None:
        """Return the BoM sun protection forecast for a station; it is optional, so failures give None."""
        product_file = f"{uv.UV_STATIONS[station].forecast_product}.xml"

        async def fetch() -> dict[str, bytes]:
            return await async_fetch_bom_products(self.hass, (product_file,), lambda name: name == product_file)

        files = await self._uv_forecast.async_get(fetch)
        if not files or product_file not in files:
            return None
        try:
            return uv.parse_uv_forecast(files[product_file], station, dt_util.utcnow())
        except ProviderUnavailableError:
            return None

    # GDACS

    async def async_fetch_regional_alerts(self) -> list[RegionalAlertItem] | None:
        """Return current GDACS Orange/Red alerts in the Australia/New Zealand region."""
        if not self._enabled(CONF_ENABLE_REGIONAL_ALERTS) or (location := self._location) is None:
            return None
        return await self._gdacs.async_get(
            lambda: gdacs.async_fetch_regional_alerts(self.session, location[0], location[1])
        )

    # Air quality

    async def async_fetch_air_quality(self) -> list[AirQualityStationData]:
        """Return stations from the state environment agency (NSW, QLD, ACT)."""
        if not self._enabled(CONF_ENABLE_AIR_QUALITY, au_only=True) or (location := self._location) is None:
            return []
        fetchers = {
            STATE_NSW: lambda: self._async_nsw_air(location),
            STATE_QLD: self._async_qld_air,
            STATE_ACT: self._async_act_air,
        }
        if (fetch := fetchers.get(self.state_code)) is None:
            return []
        return await self._air_quality.async_get(fetch) or []

    async def _async_nsw_air(self, location: tuple[float, float]) -> list[AirQualityStationData]:
        sites = await self._nsw_sites.async_get(
            lambda: self.async_fetch_feed_json(air_quality.NSW_SITES_URL, "NSW air quality sites")
        )
        if sites is None:
            raise ProviderUnavailableError("NSW air quality site list unavailable")
        nearest = air_quality.nearest_nsw_sites(sites, *location)
        if not nearest:
            return []
        body = air_quality.nsw_observation_request(nearest, dt_util.now().date())
        observations = await self.async_post_json(air_quality.NSW_OBSERVATIONS_URL, body, "NSW air quality")
        return air_quality.parse_nsw(nearest, observations)

    async def _async_qld_air(self) -> list[AirQualityStationData]:
        text = await self.async_fetch_feed_text(air_quality.QLD_AIR_QUALITY_URL, "Queensland air quality")
        return air_quality.parse_qld(text)

    async def _async_act_air(self) -> list[AirQualityStationData]:
        records = await self.async_fetch_feed_json(air_quality.ACT_AIR_QUALITY_URL, "ACT air quality")
        return air_quality.parse_act(records)
