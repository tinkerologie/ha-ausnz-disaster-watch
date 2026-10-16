"""Regression tests for state feed filtering and level mapping (#14, #27).

Fixtures follow the live payload shapes captured on 2026-10-16.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock

import pytest

from custom_components.ausnz_disaster_watch.const import STATE_ACT, STATE_SA, STATE_VIC
from custom_components.ausnz_disaster_watch.fire_districts import find_district, load_fire_districts
from custom_components.ausnz_disaster_watch.models import HazardType, WarningLevel
from custom_components.ausnz_disaster_watch.providers import ACTHazardProvider, SAHazardProvider, VictoriaHazardProvider
from custom_components.ausnz_disaster_watch.providers.base import BaseHazardProvider
from homeassistant.core import HomeAssistant

# --- Fire weather districts (#14) ---------------------------------------------------------


@pytest.mark.parametrize(
    ("lat", "lon", "expected"),
    [
        (-31.95, 115.86, "WA_FW091"),  # Perth: Perth Inner
        (-32.0, 115.52, "WA_FW092"),  # Rottnest Island
        (-30.75, 121.47, "WA_FW061"),  # Kalgoorlie: South Goldfields
        (-33.95, 115.07, "WA_FW069"),  # Margaret River: Capes
        (-14.0, 126.5, "WA_FW041"),  # North Kimberley
        (-31.95, 115.6, "WA_FW092"),  # offshore, within range of Rottnest
        (-33.87, 151.2, None),  # Sydney
    ],
)
def test_wa_fire_district_lookup(lat: float, lon: float, expected: str | None) -> None:
    """The bundled BoM polygons resolve a location to its WA fire weather district."""
    districts = load_fire_districts("wa_fire_districts")
    assert len(districts) == 49
    assert find_district(districts, lat, lon) == expected


def test_find_district_honours_holes_and_degenerate_edges() -> None:
    """Even-odd rings exclude holes; a repeated vertex does not break the distance test."""
    outer = [[0.0, 0.0], [10.0, 0.0], [10.0, 10.0], [0.0, 10.0], [0.0, 0.0]]
    hole = [[4.0, 4.0], [6.0, 4.0], [6.0, 6.0], [4.0, 6.0], [4.0, 4.0]]
    island = [[4.5, 4.5], [4.5, 4.5], [5.5, 4.5], [5.5, 5.5], [4.5, 5.5], [4.5, 4.5]]
    districts = {"DONUT": {"name": "Donut", "rings": [outer, hole]}, "ISLAND": {"name": "Island", "rings": [island]}}

    assert find_district(districts, 1.0, 1.0) == "DONUT"
    assert find_district(districts, 5.0, 5.0) == "ISLAND"
    # Inside the hole but outside the island: nearest edge within range
    assert find_district(districts, 4.3, 4.5) == "ISLAND"
    assert find_district(districts, 4.5, 4.4) == "ISLAND"  # nearest point is the repeated vertex
    assert find_district(districts, 50.0, 50.0) is None


# --- ACT (#14) ----------------------------------------------------------------------------


def _act_item(title: str, incident_type: str, agency: str, guid: str) -> str:
    return (
        f"<item><title>{title}</title><type>{incident_type}</type><agency>{agency}</agency>"
        f"<description>Incident: {title}</description><guid>{guid}</guid>"
        '<georss:point xmlns:georss="http://www.georss.org/georss">-35.32 149.03</georss:point></item>'
    )


async def test_act_excludes_ambulance_responses(hass: HomeAssistant) -> None:
    """ACT ambulance dispatches are not hazards; <type> drives hazard reduction and type (#14)."""
    prov = ACTHazardProvider(hass, AsyncMock(), {"state": STATE_ACT})
    xml_text = (
        '<?xml version="1.0"?><rss version="2.0"><channel>'
        + _act_item("HAZARD REDUCTION BURN - DUFFY", "HAZARD REDUCTION BURN", "Fire", "016526-14102026")
        + _act_item("AMBULANCE RESPONSE - O'CONNOR", "AMBULANCE RESPONSE", "Ambulance", "074939-16102026")
        + _act_item("CARDIAC - BRUCE", "MEDICAL", "Ambulance", "074950-16102026")
        + _act_item("KAMBAH", "STRUCTURE FIRE", "Fire", "074951-16102026")
        + "</channel></rss>"
    )
    hazards = prov._parse_act_feed(xml_text)

    assert [h.id for h in hazards] == ["act_esa_016526-14102026", "act_esa_074951-16102026"]
    burn, fire = hazards
    assert burn.is_hazard_reduction is True
    assert burn.raw_properties["type"] == "HAZARD REDUCTION BURN"
    assert fire.is_hazard_reduction is False
    assert fire.hazard_type == HazardType.METROPOLITAN_FIRE  # from <type>, the title has no hint


async def test_act_tolerates_empty_type_and_agency(hass: HomeAssistant) -> None:
    """Present but empty <type>/<agency> elements do not drop the item."""
    prov = ACTHazardProvider(hass, AsyncMock(), {"state": STATE_ACT})
    xml_text = (
        '<?xml version="1.0"?><rss version="2.0"><channel><item><title>GRASS FIRE - KAMBAH</title>'
        "<guid>E1</guid><type/><agency/><georss:point xmlns:georss='http://www.georss.org/georss'>"
        "-35.38 149.06</georss:point></item></channel></rss>"
    )
    assert [h.id for h in prov._parse_act_feed(xml_text)] == ["act_esa_E1"]


# --- SA (#27) -----------------------------------------------------------------------------

_SA_ENTRY = """
  <entry>
    <id>{id}</id>
    <title type="text">{title}</title>
    <updated>2026-10-16T08:06:24+10:30</updated>
    <content type="text/xml">
      <alert xmlns="urn:oasis:names:tc:emergency:cap:1.2">
        <identifier>{id}</identifier>
        <sender>emergency.services@eso.sa.gov.au</sender>
        <info>
          <event>Grass Fire</event>
          <urgency>Unknown</urgency>
          <severity>Unknown</severity>
          <senderName>South Australian Country Fire Service</senderName>
          <headline>{headline}</headline>
          <web>https://www.cfs.sa.gov.au/incidents</web>
          <parameter><valueName>Status</valueName><value>Going</value></parameter>
          {level_param}
          <area><areaDesc>{id}</areaDesc><circle>-34.83,138.50 0.0</circle></area>
        </info>
      </alert>
    </content>
  </entry>
"""


def _sa_entry(entry_id: str, level: str | None, title: str = "GRASS FIRE : TEST", headline: str = "") -> str:
    level_param = (
        f"<parameter><valueName>WarningLevel</valueName><value>{level}</value></parameter>" if level is not None else ""
    )
    return _SA_ENTRY.format(id=entry_id, title=title, headline=headline or title, level_param=level_param)


async def test_sa_maps_cap_warning_level_parameter(hass: HomeAssistant) -> None:
    """SA levels come from the CAP WarningLevel parameter, not cap:severity (#27)."""
    prov = SAHazardProvider(hass, AsyncMock(), {"state": STATE_SA})
    xml_text = (
        '<?xml version="1.0" encoding="UTF-8"?><feed xmlns="http://www.w3.org/2005/Atom">'
        + _sa_entry("ew", "Emergency Warning")
        + _sa_entry("wa", "Watch and Act")
        + _sa_entry("adv", "Advice")
        # A plain incident stays Information even when its text contains a level word
        + _sa_entry("inc", "Incident", title="EMERGENCY SERVICES CALL : LARGS BAY")
        # No parameter: fall back to the headline, then the title
        + _sa_entry("hl", None, headline="Bushfire Watch and Act Message - Coles")
        + _sa_entry("none", None, title="STRUCTURE FIRE : LARGS BAY")
        + "</feed>"
    )
    hazards = {h.id: h for h in prov._parse_cap_feed(xml_text)}

    assert {key: h.warning_level for key, h in hazards.items()} == {
        "sa_cfs_ew": WarningLevel.EMERGENCY_WARNING,
        "sa_cfs_wa": WarningLevel.WATCH_AND_ACT,
        "sa_cfs_adv": WarningLevel.ADVICE,
        "sa_cfs_inc": WarningLevel.INFORMATION,
        "sa_cfs_hl": WarningLevel.WATCH_AND_ACT,
        "sa_cfs_none": WarningLevel.INFORMATION,
    }
    ew = hazards["sa_cfs_ew"]
    assert ew.responsible_agency == "South Australian Country Fire Service"  # senderName, not the email
    assert ew.status == "Going"
    assert ew.web_url == "https://www.cfs.sa.gov.au/incidents"
    assert ew.raw_properties["warning_level"] == "Emergency Warning"


# --- VIC (#27) ----------------------------------------------------------------------------


def _vic_feature(props: dict[str, Any]) -> dict[str, Any]:
    return {"type": "Feature", "geometry": {"type": "Point", "coordinates": [144.5, -37.5]}, "properties": props}


async def test_vic_skips_burn_areas_and_bom_and_links_by_feed_type(hass: HomeAssistant) -> None:
    """VIC drops burn scars and BoM duplicates, and deep-links by feedType (#27)."""
    prov = VictoriaHazardProvider(hass, AsyncMock(), {"state": STATE_VIC})
    payload = {
        "features": [
            _vic_feature(
                {
                    "feedType": "burn-area",
                    "id": "df7aa90e5ad35876d566475191cad769",
                    "sourceOrg": "VIC/DELWP",
                    "sourceFeed": "burn-area",
                    "category1": "Burn Area",
                    "status": "Unknown",
                }
            ),
            _vic_feature(
                {
                    "feedType": "incident",
                    "id": "IDV20600/b17131b9713bfe3833558940af69288a",
                    "sourceOrg": "AU/BOM",
                    "sourceFeed": "bom-idv20600",
                    "category1": "Met",
                    "category2": "Strong Wind",
                }
            ),
            _vic_feature({"feedType": "incident", "id": "x1", "sourceFeed": "bom-idv10000", "category1": "Met"}),
            _vic_feature(
                {
                    "feedType": "incident",
                    "id": "ESTA:261016005",
                    "sourceOrg": "VIC/CFA",
                    "sourceFeed": "cfa-incident",
                    "category1": "Fire",
                    "category2": "Bushfire",
                    "status": "Safe",
                }
            ),
            _vic_feature(
                {
                    "feedType": "incident",
                    "id": 3015924,
                    "sourceOrg": "VIC/DEECA",
                    "sourceFeed": "deeca-burns",
                    "category1": "Planned Burn",
                    "category2": "Planned Burn",
                }
            ),
            _vic_feature(
                {
                    "feedType": "warning",
                    "id": "43499",
                    "sourceOrg": "EMV",
                    "sourceFeed": "cop-cap",
                    "category1": "Advice",
                    "category2": "Health",
                }
            ),
            _vic_feature(
                {
                    "feedType": "warning",
                    "id": "43500",
                    "sourceOrg": "EMV",
                    "category1": "Watch and Act",
                    "incidentList": [{"id": "ESTA:261016005"}],
                }
            ),
            _vic_feature({"feedType": "warning", "id": "43501", "category1": "Advice", "incidentList": ["bad"]}),
            _vic_feature({"id": "legacy", "category1": "Fire"}),
        ]
    }
    prov.async_fetch_json = AsyncMock(return_value=payload)
    hazards = {h.id: h for h in await prov.async_fetch_hazards()}

    base = "https://emergency.vic.gov.au/respond/#!/"
    assert {key: h.web_url for key, h in hazards.items()} == {
        "VIC_EMV_ESTA:261016005": f"{base}incident/ESTA:261016005/moreinfo",
        "VIC_EMV_3015924": f"{base}incident/3015924/moreinfo",
        "VIC_EMV_43499": f"{base}warning/43499/moreinfo",
        "VIC_EMV_43500": f"{base}incident/ESTA:261016005/warning/43500/moreinfo",
        "VIC_EMV_43501": f"{base}warning/43501/moreinfo",
        "VIC_EMV_legacy": f"{base}incident/legacy/moreinfo",
    }
    assert hazards["VIC_EMV_3015924"].is_hazard_reduction is True
    assert hazards["VIC_EMV_ESTA:261016005"].is_hazard_reduction is False


def test_act_esa_timestamp_format() -> None:
    """ACT ESA writes "15 Oct 2026 15:14:49.77" (Canberra time)."""
    assert BaseHazardProvider.parse_datetime("15 Oct 2026 15:14:49.77", "Australia/Sydney") == datetime(
        2026, 10, 15, 4, 14, 49, 770000, tzinfo=UTC
    )
    assert BaseHazardProvider.parse_datetime("15 Oct 2026 15:14:49", "Australia/Sydney") == datetime(
        2026, 10, 15, 4, 14, 49, tzinfo=UTC
    )
