"""NT provider: NT Government Fire_Incidents FeatureServer instead of the PFES file (#14, #34)."""

from __future__ import annotations

from datetime import UTC, datetime
import logging
from typing import Any
from unittest.mock import AsyncMock

import aiohttp
import pytest

from custom_components.ausnz_disaster_watch.const import STATE_NT
from custom_components.ausnz_disaster_watch.models import HazardType, WarningLevel
from custom_components.ausnz_disaster_watch.providers import NTHazardProvider
from custom_components.ausnz_disaster_watch.providers.base import ProviderUnavailableError
from custom_components.ausnz_disaster_watch.providers.nt import NT_ALERTS_URL, NT_FIRE_INCIDENTS_URL
from homeassistant.core import HomeAssistant


def _feature(
    location: str = "RUM JUNGLE",
    event: str = "Grass and Scrub Fire",
    notified: str | None = "2026-10-15T17:19:17+09:30",
    *,
    lon: float = 130.979,
    lat: float = -13.027,
    **props: Any,
) -> dict[str, Any]:
    """Return a Fire_Incidents point feature as the live service returns it (2026-10-16)."""
    properties: dict[str, Any] = {
        "objectid": 14,
        "f_category": "fire",
        "f_status": "active",
        "f_eventtype": event,
        "f_location": location,
        "f_dateclosed": None,
        "f_datenotified": notified,
        "f_lastupdate": "2026-10-15T17:24:59+09:30",
        "fire_type": event,
        "location": location,
        "status": "Active",
        "alert_level": "Advice",
        "responsible_agency": "NTFRS",
        "last_update": "15/10/2026 17:24",
        "notified": "15/10/2026 17:19",
        "closed": None,
    }
    properties.update(props)
    return {
        "type": "Feature",
        "id": properties["objectid"],
        "geometry": {"type": "Point", "coordinates": [lon, lat]},
        "properties": properties,
    }


def _collection(*features: dict[str, Any], **extra: Any) -> dict[str, Any]:
    return {"type": "FeatureCollection", "features": list(features), "exceededTransferLimit": False, **extra}


def _provider(hass: HomeAssistant, responses: dict[int, Any]) -> NTHazardProvider:
    """Return a provider whose layer queries answer from ``responses`` (an exception is raised)."""
    provider = NTHazardProvider(hass, AsyncMock(), {"state": STATE_NT})

    async def fetch(url: str, headers: dict[str, str] | None = None) -> Any:
        assert url.startswith(f"{NT_FIRE_INCIDENTS_URL}/")
        assert "f_status%3D%27active%27" in url
        result = responses[int(url.removeprefix(f"{NT_FIRE_INCIDENTS_URL}/").split("/", 1)[0])]
        if isinstance(result, BaseException):
            raise result
        return result

    provider.async_fetch_json = AsyncMock(side_effect=fetch)
    return provider


async def test_nt_reads_both_point_layers(hass: HomeAssistant) -> None:
    """Bushfires NT and NTFRS layers are merged; levels, burns and fields map as before."""
    bushfires = _collection(
        _feature(
            "Eeee Road, FLY CREEK ",
            "Bushfire",
            "2026-10-15T15:41:00+09:30",
            objectid=23,
            f_category="bushfire-advice",
            status="Going",
            alert_level="Emergency Warning",
            responsible_agency="Bushfires NT",
            f_lastupdate="2026-10-15T16:20:00+09:30",
        ),
        _feature("Weddell", "Bushfire", "2026-10-15T10:00:00+09:30", alert_level="Watch and Act"),
        _feature("Alice Springs", "Hazard Reduction Burn", "2026-10-15T09:00:00+09:30", alert_level=None),
        _feature("Katherine", "Planned Burn", None, alert_level="", f_category="notification"),
    )
    ntfrs = _collection(_feature(), _feature("Nhulunbuy", "Automatic Fire Alarm", alert_level="Notification"))
    areas = _collection(
        {
            "type": "Feature",
            "geometry": None,
            "properties": {
                "f_datenotified": "2026-10-15T15:41:00+09:30",
                "f_eventtype": "Bushfire",
                "f_location": "Eeee Road, FLY CREEK ",
                "risks": "Smoke may affect visibility",
                "what_to_do": "Stay informed",
                "current_situation": "Contained",
            },
        },
        "not a feature",
        {"type": "Feature", "properties": None},
    )
    provider = _provider(hass, {0: bushfires, 1: ntfrs, 2: areas})
    assert provider.state_code == STATE_NT

    hazards = await provider.async_fetch_hazards()
    assert len(hazards) == 6
    fly_creek, weddell, alice, katherine, rum_jungle, alarm = hazards

    assert fly_creek.title == "Bushfire - Eeee Road, FLY CREEK"
    assert fly_creek.location_name == "Eeee Road, FLY CREEK"
    assert fly_creek.warning_level == WarningLevel.EMERGENCY_WARNING
    assert fly_creek.hazard_type == HazardType.BUSHFIRE
    assert fly_creek.status == "Going"
    assert fly_creek.responsible_agency == "Bushfires NT"
    assert fly_creek.updated_at == datetime(2026, 10, 15, 6, 50, tzinfo=UTC)
    assert (fly_creek.latitude, fly_creek.longitude) == (-13.027, 130.979)
    assert fly_creek.web_url == NT_ALERTS_URL
    assert fly_creek.raw_properties == {
        "layer": "NT Bushfires",
        "risks": "Smoke may affect visibility",
        "what_to_do": "Stay informed",
        "current_situation": "Contained",
    }
    assert fly_creek.to_safe_attributes()["prop_current_situation"] == "Contained"

    assert weddell.warning_level == WarningLevel.WATCH_AND_ACT
    # No alert_level: f_category decides; "fire" is not a warning level
    assert alice.warning_level == WarningLevel.INFORMATION
    assert alice.is_hazard_reduction is True
    assert katherine.is_hazard_reduction is True
    assert katherine.warning_level == WarningLevel.INFORMATION
    assert rum_jungle.warning_level == WarningLevel.ADVICE
    assert rum_jungle.raw_properties == {"layer": "NT Fire and Rescue"}
    assert alarm.warning_level == WarningLevel.INFORMATION
    assert len({h.id for h in hazards}) == 6


async def test_nt_skips_closed_and_unlocated_incidents(hass: HomeAssistant) -> None:
    """Closed incidents never show even if the server filter is ignored; bad items are skipped."""
    features = [
        _feature("Open"),
        _feature("Closed by status", status="Closed"),
        _feature("Closed by f_status", f_status="closed"),
        _feature("Other machine status", f_status="pending"),
        {**_feature("No geometry"), "geometry": None},
        _feature("Bad latitude", lat=999.0),
        "not a feature",
        {"type": "Feature", "geometry": {"type": "Point", "coordinates": [131.0, -12.5]}, "properties": None},
    ]
    provider = _provider(hass, {0: _collection(*features), 1: _collection(), 2: _collection()})
    hazards = await provider.async_fetch_hazards()
    titles = [h.title for h in hazards]
    assert titles == ["Grass and Scrub Fire - Open", "Emergency Incident - Northern Territory"]
    # Defaults when the feature has no properties
    assert hazards[1].status == "Active"
    assert hazards[1].responsible_agency == "NT PFES"
    assert hazards[1].updated_at is None


async def test_nt_layer_failures(hass: HomeAssistant, caplog: pytest.LogCaptureFixture) -> None:
    """One failing layer keeps the other; both failing is an outage; area advice is optional (#16)."""
    good = _collection(_feature())
    bad_payloads: list[Any] = [
        [],
        {"error": {"code": 400, "message": "Invalid query"}},
        {"type": "Feature"},
        {"type": "FeatureCollection", "features": None},
    ]
    for bad in bad_payloads:
        provider = _provider(hass, {0: bad, 1: good, 2: bad})
        hazards = await provider.async_fetch_hazards()
        assert [h.responsible_agency for h in hazards] == ["NTFRS"]

    provider = _provider(hass, {0: aiohttp.ClientError("down"), 1: [], 2: aiohttp.ClientError("down")})
    with pytest.raises(ProviderUnavailableError, match="unexpected payload"):
        await provider.async_fetch_hazards()

    # A valid but empty service is an all-clear, not an outage
    provider = _provider(hass, {0: _collection(), 1: _collection(), 2: _collection()})
    assert await provider.async_fetch_hazards() == []

    # A capped response is used but logged
    provider = _provider(
        hass, {0: _collection(_feature(), exceededTransferLimit=True), 1: _collection(properties={}), 2: _collection()}
    )
    provider_props = _provider(
        hass, {0: _collection(), 1: _collection(properties={"exceededTransferLimit": True}), 2: _collection()}
    )
    with caplog.at_level(logging.WARNING):
        assert len(await provider.async_fetch_hazards()) == 1
        assert await provider_props.async_fetch_hazards() == []
    assert "NT Bushfires returned more than 2000 incidents" in caplog.text
    assert "NT Fire and Rescue returned more than 2000 incidents" in caplog.text


async def test_nt_ids_stable_and_distinct(hass: HomeAssistant) -> None:
    """IDs ignore objectid and list order, and never collide (#7)."""
    a = _feature("Litchfield Park Road, Darwin River Dam area", objectid=1)
    b = _feature("Litchfield Park Road, Darwin River Dam north", objectid=2)
    first = await _provider(hass, {0: _collection(a, b), 1: _collection(), 2: _collection()}).async_fetch_hazards()
    # The service rebuilds the layer on upload, so objectids change; IDs must not
    a2 = {**a, "properties": {**a["properties"], "objectid": 40}}
    b2 = {**b, "properties": {**b["properties"], "objectid": 41}}
    second = await _provider(hass, {0: _collection(b2, a2), 1: _collection(), 2: _collection()}).async_fetch_hazards()
    assert {h.id for h in first} == {h.id for h in second}
    assert len({h.id for h in first}) == 2

    # No notified time: same type and location at different points stay distinct
    bare = [_feature("Arnhem Hwy", notified=None, lon=lon) for lon in (131.0, 131.4)]
    hazards = await _provider(hass, {0: _collection(*bare), 1: _collection(), 2: _collection()}).async_fetch_hazards()
    assert len({h.id for h in hazards}) == 2


async def test_nt_ids_disambiguate_identical_features(hass: HomeAssistant) -> None:
    """Features sharing every identifying field (also across layers) get distinct, reorder-stable IDs."""

    async def ids(layer0: list[dict[str, Any]], layer1: list[dict[str, Any]] | None = None) -> list[str]:
        provider = _provider(hass, {0: _collection(*layer0), 1: _collection(*(layer1 or [])), 2: _collection()})
        return [h.id for h in await provider.async_fetch_hazards()]

    a = _feature("Arnhem Hwy", lon=131.0, lat=-12.5)
    b = _feature("Arnhem Hwy", lon=131.2, lat=-12.6)
    assert len(set(await ids([a, b]))) == 2
    assert set(await ids([a, b])) == set(await ids([b, a]))
    assert set(await ids([a], [b])) == set(await ids([a, b]))

    # No notified time and coordinates equal after rounding to 3 dp
    c = _feature("Arnhem Hwy", notified=None, lon=131.00001)
    d = _feature("Arnhem Hwy", notified=None, lon=131.00002)
    assert len(set(await ids([c, d]))) == 2

    # Exact duplicates fall back to an order suffix
    assert len(set(await ids([a, a, a]))) == 3


def test_nt_attribution(hass: HomeAssistant) -> None:
    """The NT provider credits the NT Government without claiming an unverified licence (#34)."""
    provider = NTHazardProvider(hass, AsyncMock(), {"state": STATE_NT})
    assert [source.key for source in provider.data_sources] == ["nt_fire_incidents"]
    assert provider.attribution is not None
    assert "Northern Territory" in provider.attribution
    assert "CC BY" not in provider.attribution
