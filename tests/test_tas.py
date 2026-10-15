"""TasALERT GeoJSON provider (#14): every alert is located; nothing is placed at Hobart."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import aiohttp
import pytest

from custom_components.ausnz_disaster_watch.const import STATE_TAS
from custom_components.ausnz_disaster_watch.models import HazardType, WarningLevel
from custom_components.ausnz_disaster_watch.providers.base import BaseHazardProvider, ProviderUnavailableError
from custom_components.ausnz_disaster_watch.providers.tas import (
    TAS_ALERT_GEOJSON_URL,
    TAS_ALERT_WEB_URL,
    TasmaniaHazardProvider,
)
from homeassistant.core import HomeAssistant


def feature(
    upstream_id: str | None,
    title: str,
    type_name: str,
    status: str = "Going",
    location: dict | None = None,
    geometry: dict | None = None,
    address: str = "PARADISE ROAD,GROVE,7109",
) -> dict:
    """Build a feature shaped like alert.tas.gov.au/data/data.geojson."""
    props = {
        "title": title,
        "status": status,
        "feedType": "incident",
        "type": {"name": type_name, "eventIcon": "fire"},
        "changed": "2026-10-15T19:38:06+00:00",
        "callTime": "2026-10-16T06:50:04+11:00",
        "number": "041585-16102026",
        "burntArea": "156.200",
        "address": address,
        "location": location if location is not None else {"lat": -43.0086, "lng": 147.0956},
    }
    if upstream_id is not None:
        props["id"] = upstream_id
    return {
        "type": "Feature",
        "geometry": geometry or {"type": "GeometryCollection", "geometries": []},
        "properties": props,
    }


async def test_tas_geojson_incidents(hass: HomeAssistant) -> None:
    """Incidents are located at their own coordinates; closed and unlocated ones are dropped."""
    payload = {
        "type": "FeatureCollection",
        "features": [
            feature("burn", "Fuel Reduction Burn", "Fuel Reduction Burn"),
            feature(
                "fire", "Bushfire - Watch and Act", "Bushfire", status="Patrol", address="LIFFEY ROAD,BRACKNELL,7302"
            ),
            feature("ew", "Emergency Warning - Bushfire", "Bushfire"),
            feature("adv", "Bushfire Advice", "Bushfire"),
            feature("closed", "Bushfire", "Bushfire", status="Safe"),
            feature("nowhere", "Bushfire", "Bushfire", location={}),
            feature(
                "geom",
                "Structure Fire",
                "Structure Fire",
                location={},
                geometry={
                    "type": "GeometryCollection",
                    "geometries": [{"type": "Point", "coordinates": [147.14, -41.38]}],
                },
                address="",
            ),
            feature(None, "Flood", "Flood", address="MAIN ROAD,HUONVILLE,7109"),
        ],
    }
    provider = TasmaniaHazardProvider(hass, AsyncMock(), {"state": STATE_TAS})
    assert provider.state_code == STATE_TAS
    provider.async_fetch_json = AsyncMock(return_value=payload)
    hazards = {h.id: h for h in await provider.async_fetch_hazards()}
    provider.async_fetch_json.assert_awaited_once()
    assert provider.async_fetch_json.await_args.args[0] == TAS_ALERT_GEOJSON_URL

    assert "tas_alert_closed" not in hazards
    assert "tas_alert_nowhere" not in hazards
    assert all((h.latitude, h.longitude) != (-42.8821, 147.3272) for h in hazards.values())  # no Hobart fallback

    burn = hazards["tas_alert_burn"]
    assert burn.is_hazard_reduction
    assert burn.title == "Fuel Reduction Burn - Grove"
    assert burn.location_name == "PARADISE ROAD,GROVE,7109"
    assert (burn.latitude, burn.longitude) == (-43.0086, 147.0956)
    assert burn.warning_level is WarningLevel.INFORMATION
    assert burn.updated_at == datetime(2026, 10, 15, 19, 38, 6, tzinfo=UTC)
    assert burn.web_url == TAS_ALERT_WEB_URL
    assert burn.raw_properties["incident_number"] == "041585-16102026"

    fire = hazards["tas_alert_fire"]
    assert fire.hazard_type is HazardType.BUSHFIRE
    assert fire.warning_level is WarningLevel.WATCH_AND_ACT
    assert fire.status == "Patrol"
    assert not fire.is_hazard_reduction
    assert hazards["tas_alert_ew"].warning_level is WarningLevel.EMERGENCY_WARNING
    assert hazards["tas_alert_adv"].warning_level is WarningLevel.ADVICE

    geom = hazards["tas_alert_geom"]
    assert (geom.latitude, geom.longitude) == (-41.38, 147.14)
    assert geom.title == "Structure Fire"
    assert geom.location_name == "Tasmania"

    # No upstream id: stable content-based id
    (no_id,) = [h for k, h in hazards.items() if k.startswith("tas_alert_") and h.title == "Flood - Huonville"]
    again = {h.title: h.id for h in provider._parse_tasalert_geojson(payload)}
    assert again["Flood - Huonville"] == no_id.id


async def test_tas_feed_failures(hass: HomeAssistant) -> None:
    """Network errors and wrong payloads are unavailable; an empty collection is an all-clear."""
    provider = TasmaniaHazardProvider(hass, AsyncMock(), {"state": STATE_TAS})
    provider.async_fetch_json = AsyncMock(side_effect=aiohttp.ClientError("down"))
    with pytest.raises(ProviderUnavailableError):
        await provider.async_fetch_hazards()
    for payload in ([], {"type": "FeatureCollection"}, {"features": None}):
        provider.async_fetch_json = AsyncMock(return_value=payload)
        with pytest.raises(ProviderUnavailableError):
            await provider.async_fetch_hazards()
    provider.async_fetch_json = AsyncMock(return_value={"type": "FeatureCollection", "features": []})
    assert await provider.async_fetch_hazards() == []


def test_act_esa_timestamp_format() -> None:
    """ACT ESA writes "15 Oct 2026 15:14:49.77" (Canberra time)."""
    assert BaseHazardProvider.parse_datetime("15 Oct 2026 15:14:49.77", "Australia/Sydney") == datetime(
        2026, 10, 15, 4, 14, 49, 770000, tzinfo=UTC
    )
    assert BaseHazardProvider.parse_datetime("15 Oct 2026 15:14:49", "Australia/Sydney") == datetime(
        2026, 10, 15, 4, 14, 49, tzinfo=UTC
    )
