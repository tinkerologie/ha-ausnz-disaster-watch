"""Parsers for the opt-in national feeds (#37), tested against recorded samples.

Fixtures in ``tests/fixtures/national`` were recorded from the live sources on 2026-10-16 and
trimmed; each XML fixture names its source in a comment. JSON fixtures: ``dea_hotspots.json``
(DEA WFS, three features), ``nsw_sites.json``/``nsw_observations.json`` (NSW air quality API),
``act_air_quality.json`` (ACT dataset 94a5-zqnn). ``IDY68027.cap.xml`` is a clearly labelled
synthetic JATWC product, because no JATWC product was live and no archive was found.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
import json
import pathlib
from typing import Any

import pytest

from custom_components.ausnz_disaster_watch.providers import air_quality, heatwave, hotspots, tsunami, uv
from custom_components.ausnz_disaster_watch.providers.base import ProviderUnavailableError
from custom_components.ausnz_disaster_watch.providers.cap import CapAlert, parse_cap

FIXTURES = pathlib.Path(__file__).parent / "fixtures" / "national"


def fixture_text(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def fixture_json(name: str) -> Any:
    return json.loads(fixture_text(name))


JATWC_NOW = datetime(2026, 10, 16, 2, 0, tzinfo=UTC)
JATWC_LAND = (FIXTURES / "IDY68027.cap.xml").read_bytes()


def jatwc_doc(product: str, *, status: str = "Actual", msg_type: str = "Alert", headline: str, expires: str) -> bytes:
    return f"""<alert xmlns="urn:oasis:names:tc:emergency:cap:1.2">
      <identifier>AusBoM-{product}-1</identifier><sent>2026-10-16T01:00:00+00:00</sent>
      <status>{status}</status><msgType>{msg_type}</msgType>
      <info><event>Tsunami</event><headline>{headline}</headline><expires>{expires}</expires>
      <area><areaDesc>Coast</areaDesc><geocode><valueName>iso</valueName><value>AU-WA</value></geocode></area>
      </info></alert>""".encode()


# JATWC


def test_jatwc_products_per_state() -> None:
    """National products always apply; ACT has no state bulletin."""
    assert tsunami.jatwc_products("qld") == ("IDY68005", "IDY68009", "IDY68020", "IDY68027")
    assert tsunami.jatwc_products("ACT") == ("IDY68005", "IDY68009", "IDY68020")


def test_is_jatwc_cap_file() -> None:
    """Both ``.cap.xml`` and ``_cap.xml`` names count; other files do not."""
    assert tsunami.is_jatwc_cap_file("IDY68027.cap.xml")
    assert tsunami.is_jatwc_cap_file("IDY68027_cap.xml")
    assert not tsunami.is_jatwc_cap_file("IDY68027.html")
    assert not tsunami.is_jatwc_cap_file("IDQ21013.cap.xml")


def test_jatwc_land_threat_from_fixture() -> None:
    """The recorded-format JATWC bulletin for Queensland is an active land threat."""
    status = tsunami.jatwc_status({"IDY68027.cap.xml": JATWC_LAND}, "QLD", JATWC_NOW)
    assert status.active is True
    assert status.threat_level == "land"
    assert status.headline == "Tsunami Warning - Land Inundation Threat for Queensland"
    assert status.expires == datetime(2026, 10, 16, 7, 10, tzinfo=UTC)
    assert status.products == ["IDY68027"]
    assert status.source == tsunami.JATWC_SOURCE


def test_jatwc_no_products_is_confirmed_clear() -> None:
    """A successful listing without products means no tsunami threat."""
    status = tsunami.jatwc_status({}, "QLD", JATWC_NOW)
    assert status.active is False
    assert status.threat_level is None
    assert status.products == []


@pytest.mark.parametrize(
    ("status", "msg_type", "headline", "expires"),
    [
        ("Test", "Alert", "Tsunami Warning - Marine Threat", "2026-10-16T07:00:00+00:00"),
        ("Actual", "Cancel", "Tsunami Warning - Marine Threat", "2026-10-16T07:00:00+00:00"),
        ("Actual", "Alert", "Cancellation of Tsunami Warning", "2026-10-16T07:00:00+00:00"),
        ("Actual", "Alert", "Tsunami Warning - Marine Threat", "2026-10-16T01:30:00+00:00"),
    ],
)
def test_jatwc_inactive_messages(status: str, msg_type: str, headline: str, expires: str) -> None:
    """Test, cancelled and expired messages are listed but not active."""
    doc = jatwc_doc("IDY68020", status=status, msg_type=msg_type, headline=headline, expires=expires)
    result = tsunami.jatwc_status({"IDY68020.cap.xml": doc}, "QLD", JATWC_NOW)
    assert result.active is False
    assert result.products == ["IDY68020"]


def test_jatwc_threat_levels_and_ranking() -> None:
    """No threat, watch and marine are derived from the text; the highest wins."""
    no_threat = jatwc_doc("IDY68009", headline="National Tsunami Bulletin", expires="2026-10-16T07:00:00+00:00")
    watch = jatwc_doc("IDY68005", headline="Tsunami Watch for Australia", expires="2026-10-16T07:00:00+00:00")
    marine = jatwc_doc("IDY68020", headline="Marine threat for parts of Australia", expires="2026-10-16T07:00:00+00:00")
    odd = jatwc_doc("IDY68020", headline="Tsunami bulletin", expires="2026-10-16T07:00:00+00:00")

    only_no_threat = tsunami.jatwc_status({"IDY68009.cap.xml": no_threat}, "QLD", JATWC_NOW)
    assert (only_no_threat.active, only_no_threat.threat_level) == (False, "no_threat")
    files = {"IDY68005.cap.xml": watch, "IDY68009.cap.xml": no_threat, "IDY68020.cap.xml": marine}
    best = tsunami.jatwc_status(files, "QLD", JATWC_NOW)
    assert (best.active, best.threat_level) == (True, "marine")
    assert tsunami.jatwc_status({"IDY68020.cap.xml": odd}, "QLD", JATWC_NOW).threat_level == "watch"


@pytest.mark.parametrize(
    ("headline", "expected"),
    [
        ("Tsunami Warning - Marine Threat for Queensland", "marine"),
        ("Tsunami Watch for Queensland and Norfolk Island", "watch"),
        ("Tsunami Warning - Land Inundation Threat for Queensland", "land"),
    ],
)
def test_jatwc_place_names_do_not_read_as_land_threat(headline: str, expected: str) -> None:
    """Only the whole word "land" is a land threat; "Queensland" or "Island" are not."""
    doc = jatwc_doc("IDY68027", headline=headline, expires="2026-10-16T07:00:00+00:00")
    assert tsunami.jatwc_status({"IDY68027.cap.xml": doc}, "QLD", JATWC_NOW).threat_level == expected


def test_jatwc_other_state_bulletin_needs_matching_area() -> None:
    """Another state's bulletin applies only if its area names this state."""
    wa = jatwc_doc("IDY68025", headline="Tsunami Warning - Marine Threat", expires="2026-10-16T07:00:00+00:00")
    assert tsunami.jatwc_status({"IDY68025.cap.xml": wa}, "QLD", JATWC_NOW).products == []
    assert tsunami.jatwc_status({"IDY68025.cap.xml": wa}, "SA", JATWC_NOW).products == []
    assert tsunami.jatwc_status({"IDY68025.cap.xml": wa}, "WA", JATWC_NOW).active is True
    # The QLD fixture's area geocode is AU-QLD, so it applies to QLD under any product id
    assert tsunami.jatwc_status({"IDY68099.cap.xml": JATWC_LAND}, "QLD", JATWC_NOW).active is True


def test_jatwc_unparsable_product_is_undetermined() -> None:
    """A present product that is not CAP raises instead of reading as clear."""
    with pytest.raises(ProviderUnavailableError):
        tsunami.jatwc_status({"IDY68020.cap.xml": b"<html>busy</html>"}, "QLD", JATWC_NOW)
    # A broken bulletin for another state does not make this state's status undetermined
    status = tsunami.jatwc_status(
        {"IDY68025.cap.xml": b"<html>busy</html>", "IDY68027.cap.xml": JATWC_LAND}, "QLD", JATWC_NOW
    )
    assert (status.active, status.products) == (True, ["IDY68027"])


# PTWC


def test_ptwc_links_from_fixture() -> None:
    """The Atom feed's CAP link is extracted."""
    assert tsunami.ptwc_cap_links(fixture_text("PHEBAtom.xml")) == [
        "https://www.tsunami.gov/events/PHEB/2026/10/13/26286001/1/WECA42/PHEBCAP.xml"
    ]


@pytest.mark.parametrize("text", ["<feed", "<rss><channel/></rss>"])
def test_ptwc_links_reject_bad_documents(text: str) -> None:
    """Invalid XML and non-Atom documents are outages."""
    with pytest.raises(ProviderUnavailableError):
        tsunami.ptwc_cap_links(text)


def _ptwc_alert(event: str, description: str, location: str = "KERMADEC ISLANDS, NEW ZEALAND") -> CapAlert:
    alert = parse_cap(f"""<alert xmlns="urn:oasis:names:tc:emergency:cap:1.2">
      <identifier>PHEB-1</identifier><sent>2026-10-16T00:00:00-00:00</sent><status>Actual</status>
      <msgType>Alert</msgType><info><event>{event}</event><headline> </headline>
      <description>{description}</description><expires>2026-10-16T06:00:00-00:00</expires>
      <parameter><valueName>EventLocationName</valueName><value>{location}</value></parameter>
      <area><areaDesc>{location}</areaDesc><circle>-30,-178 0</circle></area></info></alert>""")
    assert alert is not None
    return alert


def test_ptwc_information_statement_from_fixture_is_inactive() -> None:
    """The recorded PTWC information statement is not a threat."""
    alert = parse_cap(fixture_text("PHEBCAP.xml"))
    assert alert is not None
    status = tsunami.ptwc_status([alert], datetime(2026, 10, 13, 12, 40, tzinfo=UTC))
    assert status.active is False
    assert status.products == ["PHEB-1-26286001"]
    assert status.source == tsunami.PTWC_SOURCE


def test_ptwc_threat_naming_new_zealand_is_active() -> None:
    """A threat message whose text names New Zealand is active guidance."""
    alert = _ptwc_alert("Tsunami Threat", "Hazardous waves are possible for coasts of NEW ZEALAND")
    status = tsunami.ptwc_status([alert], datetime(2026, 10, 16, 1, 0, tzinfo=UTC))
    assert (status.active, status.threat_level) == (True, "watch")
    assert status.headline == "Tsunami Threat"


def test_ptwc_epicentre_in_new_zealand_is_not_a_threat() -> None:
    """New Zealand named only as the earthquake location does not activate the sensor."""
    alert = _ptwc_alert("Tsunami Threat", "Hazardous waves are possible for coasts of TONGA")
    assert tsunami.ptwc_status([alert], datetime(2026, 10, 16, 1, 0, tzinfo=UTC)).active is False


# Heatwave


HEATWAVE = (FIXTURES / "IDD21013.cap.xml").read_bytes()


def test_heatwave_from_fixture_skips_cancelled_district() -> None:
    """The NT product is severe for Daly; the cancelled Arnhem block is ignored."""
    status = heatwave.heatwave_status("IDD21013", HEATWAVE, datetime(2026, 10, 15, 6, 0, tzinfo=UTC))
    assert status.severity == "severe"
    assert [(a.name, a.severity) for a in status.areas] == [("Northern Territory: Daly District", "severe")]
    assert status.headline == "Severe heatwave warning for Northern Territory"
    assert status.expires == datetime(2026, 10, 16, 3, 28, 33, tzinfo=UTC)


def test_heatwave_expired_and_absent_are_none() -> None:
    """After expiry, and when the product is not issued, the severity is none."""
    later = datetime(2026, 10, 16, 4, 0, tzinfo=UTC)
    assert heatwave.heatwave_status("IDD21013", HEATWAVE, later).severity == "none"
    assert heatwave.heatwave_status("IDD21013", None, later).severity == "none"


def test_heatwave_rejects_bad_documents() -> None:
    """Invalid XML and non-CAP documents are outages, not 'none'."""
    now = datetime(2026, 10, 15, tzinfo=UTC)
    with pytest.raises(ProviderUnavailableError):
        heatwave.heatwave_status("IDQ21013", b"<alert", now)
    with pytest.raises(ProviderUnavailableError):
        heatwave.heatwave_status("IDQ21013", b"<html/>", now)


def _heatwave_doc(*infos: tuple[str, str], status: str = "Actual") -> bytes:
    blocks = "".join(
        f"<info><headline>{headline}</headline><severity>{severity}</severity>"
        "<expires>2026-10-17T00:00:00+00:00</expires><area><areaDesc>District.</areaDesc></area>"
        "<area><areaDesc> </areaDesc></area></info>"
        for headline, severity in infos
    )
    return (
        f'<alert xmlns="urn:oasis:names:tc:emergency:cap:1.2"><sent>2026-10-15T00:00:00+00:00</sent>'
        f"<status>{status}</status><msgType>Alert</msgType>{blocks}</alert>"
    ).encode()


@pytest.mark.parametrize(
    ("headline", "severity", "expected"),
    [
        ("Extreme heatwave warning for Queensland", "Extreme", "extreme"),
        ("Low intensity heatwave for Queensland", "Minor", "low_intensity"),
        ("Heatwave warning for Queensland", "Severe", "severe"),
        ("Heatwave warning for Queensland", "Moderate", "low_intensity"),
    ],
)
def test_heatwave_severity_mapping(headline: str, severity: str, expected: str) -> None:
    """Severity comes from the headline wording, else from CAP severity."""
    status = heatwave.heatwave_status(
        "IDQ21013", _heatwave_doc((headline, severity)), datetime(2026, 10, 15, tzinfo=UTC)
    )
    assert status.severity == expected
    assert [a.name for a in status.areas] == ["District"]


def test_heatwave_highest_block_wins_and_test_messages_are_ignored() -> None:
    """The highest current block sets the severity; non-Actual products are none."""
    now = datetime(2026, 10, 15, tzinfo=UTC)
    doc = _heatwave_doc(("Low intensity heatwave", "Minor"), ("Extreme heatwave warning", "Extreme"))
    assert heatwave.heatwave_status("IDQ21013", doc, now).severity == "extreme"
    test_doc = _heatwave_doc(("Extreme heatwave warning", "Extreme"), status="Test")
    assert heatwave.heatwave_status("IDQ21013", test_doc, now).severity == "none"


# UV


def test_arpansa_fixture_skips_unavailable_station() -> None:
    """Stations whose status is not ok are skipped; utcdatetime is UTC."""
    readings = uv.parse_arpansa(fixture_text("uvvalues.xml"))
    names = [r.station for r in readings]
    assert "Perth" not in names
    assert {"Brisbane", "Sydney", "Casey", "Darwin"} <= set(names)
    brisbane = next(r for r in readings if r.station == "Brisbane")
    assert brisbane.observed_at == datetime(2026, 10, 15, 22, 21, tzinfo=UTC)


def test_arpansa_rejects_bad_documents_and_values() -> None:
    """Invalid XML and wrong roots are outages; bad or negative indexes are skipped."""
    with pytest.raises(ProviderUnavailableError):
        uv.parse_arpansa("<stations")
    with pytest.raises(ProviderUnavailableError):
        uv.parse_arpansa("<html/>")
    readings = uv.parse_arpansa(
        "<stations>"
        '<location id="Sydney"><index>x</index><status>ok</status></location>'
        '<location id="Brisbane"><index>-1</index><status>ok</status></location>'
        '<location id="Darwin"><index>3</index><utcdatetime>bad</utcdatetime><status>ok</status></location>'
        "</stations>"
    )
    assert [(r.station, r.observed_at) for r in readings] == [("Darwin", None)]


def test_nearest_station_ignores_unknown_locations() -> None:
    """Antarctic and unknown stations are never picked; distance is reported."""
    readings = uv.parse_arpansa(fixture_text("uvvalues.xml"))
    nearest = uv.nearest_reading(readings, -27.5, 153.0)
    assert nearest is not None
    assert nearest[0].station == "Brisbane"
    assert nearest[1] < 5
    assert uv.nearest_reading([uv.UVReading("Casey", 1.0, None)], -27.5, 153.0) is None


def test_uv_forecast_from_fixture() -> None:
    """Today's Brisbane sun protection text and maximum index are read."""
    content = (FIXTURES / "IDZ00109.xml").read_bytes()
    forecast = uv.parse_uv_forecast(content, "Brisbane", datetime(2026, 10, 15, 23, 0, tzinfo=UTC))
    assert forecast is not None
    text, max_index = forecast
    assert text.startswith("Sun protection recommended from")
    assert max_index == int(text.rsplit("reach ", 1)[1].split()[0])
    assert uv.parse_uv_forecast(content, "Townsville", datetime(2026, 10, 15, 23, 0, tzinfo=UTC)) is None
    assert uv.parse_uv_forecast(content, "Brisbane", datetime(2026, 11, 30, tzinfo=UTC)) is None


def test_uv_forecast_edge_cases() -> None:
    """Invalid XML raises; empty text and text without a maximum are handled."""
    with pytest.raises(ProviderUnavailableError):
        uv.parse_uv_forecast(b"<product", "Brisbane", datetime(2026, 10, 15, tzinfo=UTC))
    period = '<forecast-period start-time-utc="2026-10-15T00:00:00Z" end-time-utc="2026-10-16T00:00:00Z">{}</forecast-period>'
    empty = f'<product><area description="Brisbane" type="location">{period.format("")}</area></product>'
    plain = period.format('<text type="uv_alert">Sun protection not required</text>')
    no_max = f'<product><area description="Brisbane" type="location">{plain}</area></product>'
    now = datetime(2026, 10, 15, 12, tzinfo=UTC)
    assert uv.parse_uv_forecast(empty.encode(), "Brisbane", now) is None
    assert uv.parse_uv_forecast(no_max.encode(), "Brisbane", now) == ("Sun protection not required", None)


def test_uv_observation_without_forecast() -> None:
    """The observation carries the station and rounded distance."""
    obs = uv.uv_observation(uv.UVReading("Gold Coast", 4.2, None), 12.345, None)
    assert (obs.station_id, obs.distance_km, obs.forecast, obs.forecast_max_index) == ("gold_coast", 12.3, None, None)


# DEA hotspots


def test_hotspot_query_is_bounded() -> None:
    """The query names the layer, a CRS:84 bounding box, the age and confidence filter and a cap."""
    url = hotspots.hotspot_query_url(-27.5, 153.0, 50)
    assert url.startswith(hotspots.DEA_WFS_URL)
    assert "typeNames=public%3Ahotspots_three_days" in url
    assert "BBOX%28location%2C152.4" in url
    assert "CRS%3A84" in url
    assert "hours_since_hotspot%3C24" in url
    assert "confidence%3E%3D50" in url
    assert f"count={hotspots.HOTSPOT_FEATURE_LIMIT}" in url
    assert "recent-hotspots" not in url


def test_hotspots_from_fixture_within_radius() -> None:
    """Only hotspots inside the radius are kept; sentinel values are dropped; truncation is reported."""
    result = hotspots.parse_hotspots(fixture_json("dea_hotspots.json"), -20.25, 128.9, 50)
    assert result.truncated is True
    assert result.min_confidence == hotspots.HOTSPOT_MIN_CONFIDENCE
    assert len(result.items) == 1
    item = result.items[0]
    assert item.id == "DEA_124577218"
    assert (item.confidence, item.power, item.satellite) == (100.0, None, "HIMAWARI-9")
    assert item.observed_at == datetime(2026, 10, 15, 3, 27, 31, tzinfo=UTC)
    assert item.distance_km is not None and item.distance_km < 5


def test_hotspots_malformed_features_are_skipped() -> None:
    """Features without geometry or with bad values are skipped; missing ids get a stable id."""
    payload = {
        "features": [
            {"geometry": None, "properties": {}},
            {"geometry": {"type": "Point", "coordinates": [153.0, -27.5]}, "properties": {"confidence": "bad"}},
            {
                "geometry": {"type": "Point", "coordinates": [153.0, -27.5]},
                "properties": {"confidence": 70, "satellite": " ", "power": True, "datetime": "2026-10-15T00:00:00Z"},
            },
        ],
        "numberMatched": 3,
        "numberReturned": 3,
    }
    result = hotspots.parse_hotspots(payload, -27.5, 153.0, 10)
    assert result.truncated is False
    assert len(result.items) == 1
    assert result.items[0].id.startswith("DEA_")
    assert (result.items[0].satellite, result.items[0].power) == (None, None)


def test_hotspots_bad_payload_is_unavailable() -> None:
    """A payload without a feature list is an outage."""
    with pytest.raises(ProviderUnavailableError):
        hotspots.parse_hotspots({"exceptions": ["bad filter"]}, -27.5, 153.0, 10)


# Air quality


def test_qld_air_quality_from_fixture() -> None:
    """Unavailable readings are None (never Good) and the overall rating is the worst category."""
    stations = air_quality.parse_qld(fixture_text("qld_air_quality.xml"))
    by_name = {s.station_name: s for s in stations}
    ayr = by_name["Ayr"]
    assert (ayr.pm10_measurement, ayr.pm10_rating, ayr.overall_rating) == (None, None, None)
    creek = by_name["Mountain Creek"]
    assert creek.o3_measurement == "0.026 ppm"
    assert creek.pm2_5_measurement == "4.8 µg/m³"
    assert creek.overall_rating == "Good"  # ozone is Good, the rest Very Good
    assert (creek.latitude, creek.longitude) == (-26.6917, 153.1038)
    assert creek.observed_at == datetime(2026, 10, 15, 21, 0, tzinfo=UTC)
    assert creek.source == air_quality.QLD_SOURCE


def test_qld_air_quality_bad_documents() -> None:
    """Invalid XML and wrong roots raise; a station without coordinates is skipped."""
    with pytest.raises(ProviderUnavailableError):
        air_quality.parse_qld("<airdata")
    with pytest.raises(ProviderUnavailableError):
        air_quality.parse_qld("<html/>")
    assert air_quality.parse_qld('<airdata><station name="X" measurementhour="7"/></airdata>') == []


def test_nsw_nearest_sites_and_request() -> None:
    """Sites are ordered by distance; the request covers the nearest sites and pollutants."""
    sites = [*fixture_json("nsw_sites.json"), {"Site_Id": 1, "Latitude": None}]
    nearest = air_quality.nearest_nsw_sites(sites, -33.87, 151.21)
    assert [s["Site_Id"] for s in nearest] == [1001, 39, 33]
    body = air_quality.nsw_observation_request(nearest, date(2026, 10, 16))
    assert body["Sites"] == [1001, 39, 33]
    assert body["Parameters"] == list(air_quality.NSW_PARAMETERS)
    assert (body["StartDate"], body["EndDate"]) == ("2026-10-15", "2026-10-18")
    with pytest.raises(ProviderUnavailableError):
        air_quality.nearest_nsw_sites({"error": True}, -33.87, 151.21)


def test_nsw_air_quality_from_fixture() -> None:
    """The latest reading per pollutant is kept with its category; units come from the API."""
    sites = [s for s in fixture_json("nsw_sites.json") if s["Site_Id"] in (33, 39, 1001)]
    observations = [*fixture_json("nsw_observations.json"), {"Value": 1, "Site_Id": 33}, {"Value": None}]
    stations = {s.station_id: s for s in air_quality.parse_nsw(sites, observations)}
    rozelle = stations["nsw_39"]
    assert rozelle.station_name == "Rozelle"
    assert rozelle.pm2_5_measurement is not None and rozelle.pm2_5_measurement.endswith("µg/m³")
    assert rozelle.no2_measurement is not None and rozelle.no2_measurement.endswith("pphm")
    assert rozelle.overall_rating == "Good"
    assert rozelle.observed_at is not None
    # A site without readings has no rating rather than "Good"
    assert stations["nsw_1001"].overall_rating is None
    with pytest.raises(ProviderUnavailableError):
        air_quality.parse_nsw(sites, {"error": True})


def test_act_air_quality_from_fixture() -> None:
    """One station per name, Sydney local time, AQI categories; no rating without a reading."""
    stations = air_quality.parse_act([*fixture_json("act_air_quality.json"), {"name": "Broken"}])
    assert [s.station_name for s in stations] == ["Civic", "Monash", "Florey"]
    civic = stations[0]
    assert civic.observed_at == datetime(2026, 10, 15, 14, 0, tzinfo=UTC)
    assert (civic.no2_measurement, civic.no2_rating) == (None, None)
    assert (civic.pm10_measurement, civic.pm10_rating) == ("6.48 µg/m³", "Very Good")
    assert civic.overall_rating == "Very Good"
    with pytest.raises(ProviderUnavailableError):
        air_quality.parse_act({"error": True})


def test_act_overall_rating_falls_back_to_pollutants() -> None:
    """Without a site AQI the worst pollutant category is used."""
    record = {"name": "X", "gps": {"latitude": "-35.3", "longitude": "149.1"}, "pm10_1_hr": "80", "aqi_pm10": "120"}
    assert air_quality.parse_act([record])[0].overall_rating == "Poor"


@pytest.mark.parametrize(
    ("aqi", "expected"),
    [
        (None, None),
        ("x", None),
        (-1, None),
        (10, "Very Good"),
        (50, "Good"),
        (80, "Fair"),
        (160, "Very Poor"),
        (250, "Hazardous"),
    ],
)
def test_act_category_bands(aqi: Any, expected: str | None) -> None:
    """ACT AQI bands."""
    assert air_quality.act_category(aqi) == expected


def test_worst_category_ignores_unknown() -> None:
    """Unknown and missing categories are ignored."""
    assert air_quality.worst_category([None, "Bogus", "Fair", "good"]) == "Fair"
    assert air_quality.worst_category([None, "Bogus"]) is None


def test_qld_measurement_without_value_is_unavailable() -> None:
    """A measurement element with no text reads as unavailable."""
    xml = (
        '<airdata><station name="Y" latitude="-27" longitude="153" measurementdate="2026-10-16" measurementhour="7">'
        '<measurement name="Particle PM2.5" rating_name="Good"></measurement></station></airdata>'
    )
    station = air_quality.parse_qld(xml)[0]
    assert (station.pm2_5_measurement, station.overall_rating) == (None, None)


def test_nsw_time_is_end_of_hour_in_sydney() -> None:
    """``Hour`` 8 on a date is 08:00 Sydney time."""
    when = air_quality._nsw_time({"Date": "2026-10-16", "Hour": 8})
    assert when == datetime(2026, 10, 15, 21, 0, tzinfo=UTC)
    assert air_quality._nsw_time({"Date": "bad", "Hour": 1}) is None
