"""Data source register: who publishes each upstream feed, on what terms, and how to credit it (#34).

``docs/development/DATA_SOURCES.md`` is the full register (endpoints, terms evidence, rate
limits, decisions). This module holds the part the integration needs at runtime: the
attribution text entities show and the summary diagnostics report. Keep both in step;
``tests/test_data_sources.py`` checks that every URL the code calls is in the register.

Attribution text names a licence only where the publisher grants one (status ``open``).
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import asdict, dataclass
from enum import StrEnum

REGISTER_PATH = "docs/development/DATA_SOURCES.md"


class LicenceStatus(StrEnum):
    """How far the publisher's terms allow this integration to use a source."""

    OPEN = "open"  # an open licence (e.g. CC BY) covers the feed
    RESTRICTED = "restricted"  # terms limit reuse; kept until a sanctioned alternative exists
    UNVERIFIED = "unverified"  # no licence found for the feed itself


@dataclass(frozen=True, slots=True)
class DataSource:
    """One upstream publisher/feed in the register."""

    key: str
    owner: str
    attribution: str
    licence: str
    terms_url: str
    status: LicenceStatus

    def as_dict(self) -> dict[str, str]:
        """Return a JSON-safe summary for diagnostics."""
        return {**asdict(self), "status": self.status.value}


_SOURCES = (
    DataSource(
        key="qfd_incidents",
        owner="Queensland Fire Department",
        attribution="© State of Queensland (Queensland Fire Department), CC BY 4.0",
        licence="CC BY 4.0",
        terms_url="https://www.data.qld.gov.au/dataset/queensland-fire-and-rescue-current-bushfire-incidents",
        status=LicenceStatus.OPEN,
    ),
    DataSource(
        key="guardian_ims",
        owner="Local councils (Guardian IMS dashboards by QIT Plus)",
        attribution="Local council disaster dashboard (Guardian IMS)",
        licence="Per council; e.g. Moreton Bay CC BY 4.0 excluding third-party content, Hawkesbury non-commercial",
        # Cameras, outages, roads, observations and bulletins all come from the dashboard
        terms_url="https://www.moretonbay.qld.gov.au/Council/Governance/Copyright",
        status=LicenceStatus.RESTRICTED,
    ),
    DataSource(
        key="qfd_warning_areas",
        owner="Queensland Fire Department (QFES OCS warnings, Public Safety Business Agency ArcGIS)",
        attribution="State of Queensland (Queensland Fire and Emergency Services)",
        licence="No licence published; the ArcGIS item has a disclaimer and this credit only",
        terms_url="https://www.arcgis.com/home/item.html?id=7da8fbcdd23541c4ab0464a685e2b3de",
        status=LicenceStatus.UNVERIFIED,
    ),
    DataSource(
        key="qps_warning_areas",
        owner="Queensland Police Service",
        attribution="Queensland Police Service",
        licence="No licence published for the ArcGIS layer",
        terms_url="https://www.arcgis.com/home/item.html?id=a858cd92be2d48479ae5a30d8cfce10c",
        status=LicenceStatus.UNVERIFIED,
    ),
    DataSource(
        key="nsw_rfs",
        owner="NSW Rural Fire Service",
        attribution=(
            "© State of New South Wales (NSW Rural Fire Service), CC BY 4.0. "
            "For current information go to www.rfs.nsw.gov.au"
        ),
        licence="CC BY 4.0",
        terms_url="https://www.rfs.nsw.gov.au/news-and-media/stay-up-to-date/feeds",
        status=LicenceStatus.OPEN,
    ),
    DataSource(
        key="vic_emergency",
        owner="Emergency Management Victoria (State of Victoria)",
        attribution="VicEmergency, Emergency Management Victoria",
        licence="All rights reserved; prior written permission required",
        terms_url="https://emergency.vic.gov.au/about-this-site/terms-of-use",
        status=LicenceStatus.RESTRICTED,
    ),
    DataSource(
        key="wa_emergency",
        owner="Department of Fire and Emergency Services (WA)",
        attribution=(
            "© State of Western Australia acting through the Department of Fire and Emergency Services. "
            "For current information go to www.emergency.wa.gov.au"
        ),
        licence="CC BY-ND 4.0; no monitoring or copying except the designated RSS, CAP-AU and SLIP feeds",
        terms_url="https://www.emergency.wa.gov.au/about",
        status=LicenceStatus.RESTRICTED,
    ),
    DataSource(
        key="sa_eso_cap",
        owner="Government of South Australia (SA Country Fire Service and SA State Emergency Service)",
        attribution="Government of South Australia (SA Country Fire Service and SA State Emergency Service)",
        licence="CFS incident feeds are CC BY-NC-ND 4.0; no terms found for cap-au.xml itself",
        terms_url="https://data.sa.gov.au/data/dataset/south-australian-country-fire-service-current-incidents-rss-feed",
        status=LicenceStatus.RESTRICTED,
    ),
    DataSource(
        key="sa_ses_warnings",
        owner="SA State Emergency Service",
        attribution="SA State Emergency Service",
        licence='ArcGIS item licence "Public Use"; no licence terms published',
        terms_url="https://ses.geohub.sa.gov.au/portal/home/item.html?id=0bc5049da77b4035b67f8ade3f20a034",
        status=LicenceStatus.UNVERIFIED,
    ),
    DataSource(
        key="act_esa",
        owner="ACT Emergency Services Agency",
        attribution="ACT Emergency Services Agency",
        licence="No licence published for the incident feeds",
        terms_url="https://esa.act.gov.au/disclaimer",
        status=LicenceStatus.UNVERIFIED,
    ),
    DataSource(
        key="tasalert",
        owner="TasALERT (Tasmanian Government)",
        attribution="TasALERT, Tasmanian Government",
        licence="Feed access by permission (info@alert.tas.gov.au); state content non-commercial",
        terms_url="https://alert.tas.gov.au/about-app",
        status=LicenceStatus.RESTRICTED,
    ),
    DataSource(
        key="nt_fire_incidents",
        owner="Northern Territory Government (NT Police, Fire and Emergency Services)",
        attribution="Northern Territory Government (NT Police, Fire and Emergency Services)",
        licence="No licence published for the Fire_Incidents service",
        terms_url="https://gis-d.nt.gov.au/arcgis/rest/services/Hosted/Fire_Incidents/FeatureServer",
        status=LicenceStatus.UNVERIFIED,
    ),
    DataSource(
        key="geonet",
        owner="GeoNet (Earth Sciences New Zealand)",
        attribution="GeoNet, Earth Sciences New Zealand, CC BY 3.0 NZ",
        licence="CC BY 3.0 NZ",
        terms_url="https://www.geonet.org.nz/policy",
        status=LicenceStatus.OPEN,
    ),
    DataSource(
        key="ga_earthquakes",
        owner="Geoscience Australia",
        attribution="© Commonwealth of Australia (Geoscience Australia), CC BY 4.0",
        licence="CC BY 4.0",
        terms_url="https://www.ga.gov.au/copyright",
        status=LicenceStatus.OPEN,
    ),
    DataSource(
        key="nzta_roads",
        owner="NZ Transport Agency Waka Kotahi",
        attribution="NZ Transport Agency Waka Kotahi",
        licence="No licence published (data.govt.nz: No License Provided)",
        terms_url="https://www.nzta.govt.nz/about-us/about-this-site/copyright/",
        status=LicenceStatus.UNVERIFIED,
    ),
    DataSource(
        key="nema_cap",
        owner="National Emergency Management Agency (New Zealand)",
        attribution="National Emergency Management Agency (NZ), CC BY 4.0",
        licence="CC BY 4.0",
        terms_url="https://www.civildefence.govt.nz/about/copyright",
        status=LicenceStatus.OPEN,
    ),
    DataSource(
        key="metservice_cap",
        owner="Meteorological Service of New Zealand Limited",
        attribution="MetService, CC BY 4.0",
        licence="CC BY 4.0 (CAP feed), subject to the CAP Code of Practice",
        terms_url="https://www.metservice.com/about/common-alerting-protocol",
        status=LicenceStatus.OPEN,
    ),
    # Statewide road feeds (#29)
    DataSource(
        key="livetraffic_nsw",
        owner="Transport for NSW",
        attribution="© Transport for NSW (Live Traffic NSW), CC BY 4.0",
        licence="CC BY 4.0",
        terms_url="https://opendata.transport.nsw.gov.au/dataset/live-traffic-hazards",
        status=LicenceStatus.OPEN,
    ),
    DataSource(
        key="qldtraffic_cameras",
        owner="Department of Transport and Main Roads (QLDTraffic); images by TMR, Transport for NSW or councils",
        attribution="© State of Queensland (Department of Transport and Main Roads), QLDTraffic cameras, CC BY 4.0",
        licence="CC BY 4.0 (QLDTraffic API specification); each image's owner is named in the feed",
        terms_url="https://www.data.qld.gov.au/dataset/131940-traffic-and-travel-information-geojson-api",
        status=LicenceStatus.OPEN,
    ),
    DataSource(
        key="nzta_cameras",
        owner="NZ Transport Agency Waka Kotahi",
        attribution="NZ Transport Agency Waka Kotahi traffic cameras",
        licence="No licence published (data.govt.nz: No License Provided)",
        terms_url="https://www.nzta.govt.nz/about-us/about-this-site/copyright/",
        status=LicenceStatus.UNVERIFIED,
    ),
    DataSource(
        key="qldtraffic_events",
        owner="Department of Transport and Main Roads (QLDTraffic)",
        attribution="© State of Queensland (Department of Transport and Main Roads), QLDTraffic, CC BY 4.0",
        licence="CC BY 4.0 (the keyless events_v2.geojson path is not in the API documentation)",
        terms_url="https://www.data.qld.gov.au/dataset/131940-traffic-and-travel-information-geojson-api",
        status=LicenceStatus.OPEN,
    ),
    DataSource(
        key="dtp_vic_roads",
        owner="Department of Transport and Planning (Victoria)",
        attribution="© State of Victoria (Department of Transport and Planning), CC BY 4.0",
        licence="CC BY 4.0; free API key",
        terms_url="https://opendata.transport.vic.gov.au/dataset/unplanned-disruptions-road",
        status=LicenceStatus.OPEN,
    ),
    DataSource(
        key="traffic_sa",
        owner="Department for Infrastructure and Transport (South Australia)",
        attribution="© Government of South Australia (Department for Infrastructure and Transport), Traffic SA, CC BY",
        licence="CC BY (data.sa.gov.au; data.gov.au lists CC BY 3.0 AU)",
        terms_url="https://data.sa.gov.au/data/dataset/roadworks-and-incidents-real-time-information",
        status=LicenceStatus.OPEN,
    ),
    DataSource(
        key="mrwa_webeoc",
        owner="Main Roads Western Australia",
        attribution="© Commissioner of Main Roads Western Australia, CC BY 4.0",
        licence="CC BY 4.0",
        terms_url="https://catalogue.data.wa.gov.au/dataset/mrwa-webeoc-road-closures",
        status=LicenceStatus.OPEN,
    ),
    DataSource(
        key="nt_road_report",
        owner="Northern Territory Government (Department of Logistics and Infrastructure)",
        attribution="NT Road Report, Northern Territory Government",
        licence="No licence or terms published for the feed",
        terms_url="https://roadreport.nt.gov.au",
        status=LicenceStatus.UNVERIFIED,
    ),
    DataSource(
        key="bom_wmo",
        owner="Australian Government Bureau of Meteorology (via WMO Severe Weather Information Centre)",
        attribution="Australian Government Bureau of Meteorology (www.bom.gov.au), via WMO SWIC",
        licence="BoM: personal and non-commercial use; WMO SWIC: free reuse crediting the issuing service",
        terms_url="https://www.bom.gov.au/copyright",
        status=LicenceStatus.RESTRICTED,
    ),
    # Fire danger outlook, total fire bans and NZ fire season (#28)
    DataSource(
        key="bom_fire_danger",
        owner="Australian Government Bureau of Meteorology",
        attribution="Fire danger forecast: Australian Government Bureau of Meteorology (www.bom.gov.au)",
        licence="BoM copyright: personal and non-commercial use",
        terms_url="https://www.bom.gov.au/copyright",
        status=LicenceStatus.RESTRICTED,
    ),
    DataSource(
        key="cfa_fire_bans",
        owner="Country Fire Authority",
        attribution="© State of Victoria (Country Fire Authority), CC BY 4.0",
        licence="CC BY 4.0",
        terms_url="https://discover.data.vic.gov.au/dataset/cfa-data-feeds-for-incidents-total-fire-bans-fire-danger-ratings-and-latest-news",
        status=LicenceStatus.OPEN,
    ),
    DataSource(
        key="sa_cfs_fire_danger",
        owner="SA Country Fire Service",
        attribution="Government of South Australia (SA Country Fire Service)",
        licence="No terms for fireDangerRating.xml; neighbouring CFS feeds are CC BY-NC-ND 4.0",
        terms_url="https://data.sa.gov.au/data/dataset/south-australian-country-fire-service-current-incidents-rss-feed",
        status=LicenceStatus.RESTRICTED,
    ),
    DataSource(
        key="abs_lga",
        owner="Australian Bureau of Statistics",
        attribution="Local government areas © Australian Bureau of Statistics, CC BY 4.0",
        licence="CC BY 4.0",
        terms_url="https://www.abs.gov.au/website-privacy-copyright-and-disclaimer",
        status=LicenceStatus.OPEN,
    ),
    DataSource(
        key="fenz_fire_season",
        owner="Fire and Emergency New Zealand",
        attribution="Fire and Emergency New Zealand",
        licence="No licence published for the fire season and Section 52 layers",
        terms_url="https://www.fireandemergency.nz/about-us/copyright/",
        status=LicenceStatus.UNVERIFIED,
    ),
    # Electricity distributor outage feeds (#36); opt-in ones need the extra outage feeds option
    DataSource(
        key="endeavour_outages",
        owner="Endeavour Energy",
        attribution=(
            "Contains information from Endeavour Energy Open Data, made available under the "
            "Open Database Licence (ODbL) v1.0"
        ),
        licence="ODbL 1.0",
        terms_url="https://data.endeavourenergy.com.au/explore/dataset/outagecustomerlive/information/",
        status=LicenceStatus.OPEN,
    ),
    DataSource(
        key="essential_outages",
        owner="Essential Energy",
        attribution="Outage data: Essential Energy",
        licence="None published; the website has no terms of use",
        terms_url="https://www.essentialenergy.com.au",
        status=LicenceStatus.UNVERIFIED,
    ),
    DataSource(
        key="tasnetworks_outages",
        owner="TasNetworks",
        attribution="Outage data: TasNetworks",
        licence="None published; TasNetworks retains copyright of the site content",
        terms_url="https://www.tasnetworks.com.au/disclaimer",
        status=LicenceStatus.UNVERIFIED,
    ),
    DataSource(
        key="mainpower_outages",
        owner="MainPower New Zealand",
        attribution="Outage data: MainPower",
        licence="None published",
        terms_url="https://outages.mainpower.co.nz",
        status=LicenceStatus.UNVERIFIED,
    ),
    DataSource(
        key="unison_outages",
        owner="Unison Networks",
        attribution="Outage data: Unison Networks",
        licence="None published",
        terms_url="https://www.unison.co.nz",
        status=LicenceStatus.UNVERIFIED,
    ),
    DataSource(
        key="western_power_outages",
        owner="Western Power",
        attribution="Outage data: Western Power",
        licence="Website terms: personal, non-commercial use relating to your own energy consumption",
        terms_url="https://www.westernpower.com.au/terms--conditions/",
        status=LicenceStatus.RESTRICTED,
    ),
    DataSource(
        key="powerco_outages",
        owner="Powerco",
        attribution="Outage data: Powerco",
        licence="Website terms: no public purpose or commercial gain",
        terms_url="https://www.powerco.co.nz/terms-of-use",
        status=LicenceStatus.RESTRICTED,
    ),
    # Opt-in Open-Meteo forecast features (#38, #39, #40); the free API is non-commercial only
    DataSource(
        key="open_meteo_forecast",
        owner="Open-Meteo",
        attribution="Weather data by Open-Meteo.com, CC BY 4.0",
        licence="CC BY 4.0; free API non-commercial only, under 10,000 calls a day",
        terms_url="https://open-meteo.com/en/terms",
        status=LicenceStatus.OPEN,
    ),
    DataSource(
        key="open_meteo_flood",
        owner="Open-Meteo, with GloFAS data from the Copernicus Emergency Management Service",
        attribution="Flood data by Open-Meteo.com (GloFAS), CC BY 4.0",
        licence="CC BY 4.0; free API non-commercial only, under 10,000 calls a day",
        terms_url="https://open-meteo.com/en/licence",
        status=LicenceStatus.OPEN,
    ),
    DataSource(
        key="ecmwf_aifs",
        owner="ECMWF, served by Open-Meteo",
        attribution="ECMWF AIFS, CC BY 4.0",
        licence="CC BY 4.0 (ECMWF open data); Open-Meteo free API non-commercial only",
        terms_url="https://www.ecmwf.int/en/forecasts/datasets/open-data",
        status=LicenceStatus.OPEN,
    ),
    DataSource(
        key="google_weathernext2",
        owner="Google DeepMind, served by Open-Meteo",
        attribution="Google WeatherNext 2",
        licence="Not verified: Open-Meteo states none; Google's real-time experimental data terms may apply",
        terms_url="https://open-meteo.com/en/docs/google-weathernext-api",
        status=LicenceStatus.UNVERIFIED,
    ),
    # Opt-in river gauges (#31)
    DataSource(
        key="river_qld_wmip",
        owner="Queensland Government (Water Monitoring Information Portal)",
        attribution="© State of Queensland, Water Monitoring Information Portal, CC BY 4.0",
        licence="CC BY 4.0",
        terms_url="https://www.qld.gov.au/legal/disclaimer",
        status=LicenceStatus.OPEN,
    ),
    DataSource(
        key="river_waternsw",
        owner="WaterNSW",
        attribution="© State Government of NSW and WaterNSW, CC BY",
        licence="CC BY (3.0 or 4.0; listings differ)",
        terms_url="https://data.gov.au/data/dataset/nsw-real-time-water",
        status=LicenceStatus.OPEN,
    ),
    DataSource(
        key="river_hbrc_hilltop",
        owner="Hawke's Bay Regional Council",
        attribution="Hawke's Bay Regional Council, CC BY",
        licence="CC BY 3.0 or 4.0 NZ",
        terms_url="https://www.hbrc.govt.nz/our-council/open-data/",
        status=LicenceStatus.OPEN,
    ),
    DataSource(
        key="river_nz_hilltop",
        owner="NZ regional councils (Hilltop servers)",
        attribution="New Zealand regional councils",
        licence="Not verified: no licence stated for the Hilltop servers",
        terms_url="https://hilltop.gw.govt.nz/Data.hts",
        status=LicenceStatus.UNVERIFIED,
    ),
    # Opt-in dam and weir storages; each entity shows its data owner's attribution
    DataSource(
        key="bom_water_storages",
        owner="Water agencies reporting to the Bureau of Meteorology (Water Data Online)",
        attribution="Data owner's credit, CC BY 3.0 AU, via Bureau of Meteorology Water Data Online",
        licence="CC BY 3.0 AU, per data owner (owners with other terms are excluded)",
        terms_url="https://www.bom.gov.au/waterdata/wiski-web-public/copyright.htm",
        status=LicenceStatus.OPEN,
    ),
    # Opt-in national and regional feeds (#37)
    DataSource(
        key="bom_ftp",
        owner="Australian Government Bureau of Meteorology (anonymous FTP products)",
        attribution="Australian Government Bureau of Meteorology (www.bom.gov.au)",
        licence="BoM: personal and non-commercial use",
        terms_url="https://www.bom.gov.au/copyright",
        status=LicenceStatus.RESTRICTED,
    ),
    DataSource(
        key="ptwc",
        owner="NOAA National Weather Service Pacific Tsunami Warning Center",
        attribution="NOAA Pacific Tsunami Warning Center (US Government work, public domain; no licence needed)",
        licence="Public domain (US Government work)",
        terms_url="https://www.weather.gov/disclaimer",
        status=LicenceStatus.OPEN,
    ),
    DataSource(
        key="dea_hotspots",
        owner="Geoscience Australia (Digital Earth Australia Hotspots)",
        attribution="Digital Earth Australia Hotspots, Geoscience Australia, CC BY 4.0",
        licence="CC BY 4.0; not for safety-of-life decisions",
        terms_url="https://www.ga.gov.au/copyright",
        status=LicenceStatus.OPEN,
    ),
    DataSource(
        key="arpansa_uv",
        owner="Australian Radiation Protection and Nuclear Safety Agency (ARPANSA)",
        attribution="UV observations courtesy of ARPANSA",
        licence="Acknowledge ARPANSA and notify ARPANSA of the application; no retransmission or commercial use",
        terms_url="https://www.arpansa.gov.au/our-services/monitoring/ultraviolet-radiation-monitoring/ultraviolet-radation-data-information",
        status=LicenceStatus.RESTRICTED,
    ),
    DataSource(
        key="gdacs",
        owner="European Commission Joint Research Centre (GDACS)",
        attribution="Global Disaster Alert and Coordination System (GDACS), European Union / JRC; indicative only",
        licence="No GDACS licence found; the RSS <copyright> says public domain; EC legal notice applies",
        terms_url="https://www.gdacs.org/About/termofuse.aspx",
        status=LicenceStatus.UNVERIFIED,
    ),
    DataSource(
        key="nsw_air_quality",
        owner="NSW Department of Climate Change, Energy, the Environment and Water",
        attribution="NSW Department of Climate Change, Energy, the Environment and Water, CC BY 4.0",
        licence="CC BY 4.0",
        terms_url="https://data.nsw.gov.au/data/dataset/nsw-air-quality-data-services",
        status=LicenceStatus.OPEN,
    ),
    DataSource(
        key="qld_air_quality",
        owner="Queensland Government (Department of the Environment)",
        attribution="© State of Queensland, CC BY 4.0",
        licence="CC BY 4.0",
        terms_url="https://www.data.qld.gov.au/dataset/air-quality-monitoring-live-data-feed",
        status=LicenceStatus.OPEN,
    ),
    DataSource(
        key="act_air_quality",
        owner="ACT Government",
        attribution="ACT Government, CC BY 4.0",
        licence="CC BY 4.0",
        terms_url="https://www.data.act.gov.au/d/94a5-zqnn",
        status=LicenceStatus.OPEN,
    ),
    # Emergency broadcaster (#73): bundled at build time, streams are only linked
    DataSource(
        key="radio_browser",
        owner="Radio Browser community directory",
        attribution="Station directory: Radio Browser (public domain; no licence needed)",
        licence="Public domain dedication of the directory data; API free for any software",
        terms_url="https://www.radio-browser.info/",
        status=LicenceStatus.OPEN,
    ),
    DataSource(
        key="abc_local_radio",
        owner="Australian Broadcasting Corporation (ABC Local Radio)",
        attribution="ABC Local Radio, Australian Broadcasting Corporation",
        licence="ABC Terms of Use: ABC content for personal, non-commercial use; the stream is linked, not copied",
        terms_url="https://help.abc.net.au/hc/en-us/articles/360001548096-ABC-Terms-of-Use",
        status=LicenceStatus.RESTRICTED,
    ),
    DataSource(
        key="rnz_national",
        owner="Radio New Zealand (RNZ)",
        attribution="RNZ National, Radio New Zealand",
        licence="RNZ Terms of Use: personal listening only, no rebroadcast; the stream is linked, not copied",
        terms_url="https://www.rnz.co.nz/about/legal",
        status=LicenceStatus.RESTRICTED,
    ),
)

# Register keys of the national feeds, by the option that enables each one
NATIONAL_FEED_SOURCES: dict[str, tuple[str, ...]] = {
    "enable_tsunami": ("bom_ftp", "ptwc"),
    "enable_satellite_hotspots": ("dea_hotspots",),
    "enable_heatwave": ("bom_ftp",),
    "enable_uv": ("arpansa_uv", "bom_ftp"),
    "enable_state_air_quality": ("nsw_air_quality", "qld_air_quality", "act_air_quality"),
    "enable_regional_alerts": ("gdacs",),
}

DATA_SOURCES: dict[str, DataSource] = {source.key: source for source in _SOURCES}

# Provider class name -> register keys of the sources it reads
PROVIDER_SOURCES: dict[str, tuple[str, ...]] = {
    "QueenslandHazardProvider": ("qfd_incidents", "qfd_warning_areas", "qps_warning_areas", "guardian_ims"),
    "NSWHazardProvider": ("nsw_rfs", "guardian_ims"),
    "VictoriaHazardProvider": ("vic_emergency",),
    "WAHazardProvider": ("wa_emergency",),
    "SAHazardProvider": ("sa_eso_cap", "sa_ses_warnings"),
    "ACTHazardProvider": ("act_esa",),
    "TasmaniaHazardProvider": ("tasalert",),
    "NTHazardProvider": ("nt_fire_incidents",),
    "NZHazardProvider": ("geonet", "nema_cap", "metservice_cap", "nzta_roads"),
    "BoMHazardProvider": ("bom_wmo",),
    "GAEarthquakeProvider": ("ga_earthquakes",),
    "NationalHazardProvider": tuple(dict.fromkeys(key for keys in NATIONAL_FEED_SOURCES.values() for key in keys)),
    # Statewide road feeds (#29); TasALERT road closures fall under the TasALERT terms
    "NSWRoadProvider": ("livetraffic_nsw",),
    "QueenslandRoadProvider": ("qldtraffic_events",),
    "VictoriaRoadProvider": ("dtp_vic_roads",),
    "SARoadProvider": ("traffic_sa",),
    "WARoadProvider": ("mrwa_webeoc",),
    "NTRoadProvider": ("nt_road_report",),
    "TasmaniaRoadProvider": ("tasalert",),
    "EndeavourOutageSource": ("endeavour_outages",),
    "EssentialEnergyOutageSource": ("essential_outages",),
    "TasNetworksOutageSource": ("tasnetworks_outages",),
    "MainPowerOutageSource": ("mainpower_outages",),
    "UnisonOutageSource": ("unison_outages",),
    "WesternPowerOutageSource": ("western_power_outages",),
    "PowercoOutageSource": ("powerco_outages",),
    # Road and flood camera catalogues (#70); the provider reports only its enabled networks
    "CameraCatalogueProvider": ("qldtraffic_cameras", "nzta_cameras"),
}


# Forecast feature -> register keys (these are not hazard providers)
FORECAST_SOURCES: dict[str, tuple[str, ...]] = {
    "weather_signals": ("open_meteo_forecast",),
    "river_forecast": ("open_meteo_flood",),
    "ai_ensemble": ("open_meteo_forecast", "ecmwf_aifs"),
    "ai_weathernext": ("google_weathernext2",),
}


# Emergency broadcaster sources by table country (#73)
BROADCASTER_SOURCES: dict[str, tuple[str, ...]] = {
    "AU": ("abc_local_radio", "radio_browser"),
    "NZ": ("rnz_national", "radio_browser"),
}


# Fire danger sources per jurisdiction of the location's fire weather district (#28)
FIRE_SOURCES: dict[str, tuple[str, ...]] = {
    "NSW": ("bom_fire_danger", "nsw_rfs"),
    "ACT": ("bom_fire_danger", "act_esa"),
    "VIC": ("bom_fire_danger", "cfa_fire_bans"),
    "SA": ("bom_fire_danger", "sa_cfs_fire_danger"),
    "WA": ("bom_fire_danger", "wa_emergency", "abs_lga"),
    "QLD": ("bom_fire_danger",),
    "NT": ("bom_fire_danger",),
    "TAS": ("bom_fire_danger",),
    "NZ": ("fenz_fire_season",),
}


def sources_for_fire(jurisdiction: str) -> tuple[DataSource, ...]:
    """Return the register entries the fire danger outlook reads for a jurisdiction."""
    return tuple(DATA_SOURCES[key] for key in FIRE_SOURCES.get(jurisdiction, ()))


def sources_for_broadcaster(country: str) -> tuple[DataSource, ...]:
    """Return the register entries behind the emergency broadcaster of a country (AU or NZ)."""
    return tuple(DATA_SOURCES[key] for key in BROADCASTER_SOURCES.get(country, ()))


# Opt-in features with their own coordinator -> register keys. Their entities carry their
# own attribution, so these are listed in diagnostics but not in the entry's attribution.
FEATURE_SOURCES: dict[str, tuple[str, ...]] = {
    "dam_storages": ("bom_water_storages",),
}


def sources_for_feature(feature: str) -> tuple[DataSource, ...]:
    """Return the register entries an opt-in feature with its own coordinator reads."""
    return tuple(DATA_SOURCES[key] for key in FEATURE_SOURCES[feature])


# River gauge services (rivers.GaugeSite.source) -> register keys. Hawke's Bay has its own
# licence; the other Hilltop servers share one unverified entry.
RIVER_GAUGE_SOURCES: dict[str, str] = {
    "qld": "river_qld_wmip",
    "nsw": "river_waternsw",
    "hilltop_hbrc": "river_hbrc_hilltop",
}


def sources_for_river_gauges(gauge_sources: Iterable[str]) -> tuple[DataSource, ...]:
    """Return the register entries of the gauge services in use, once each, in order (#21)."""
    keys = (
        RIVER_GAUGE_SOURCES.get(source, "river_nz_hilltop" if source.startswith("hilltop_") else "")
        for source in gauge_sources
    )
    return tuple(DATA_SOURCES[key] for key in dict.fromkeys(keys) if key)


def sources_for_forecast(*features: str) -> tuple[DataSource, ...]:
    """Return the register entries for forecast features, in order."""
    return tuple(DATA_SOURCES[key] for feature in features for key in FORECAST_SOURCES[feature])


def sources_for_provider(provider_name: str) -> tuple[DataSource, ...]:
    """Return the register entries for a provider class name (none for unknown providers)."""
    return tuple(DATA_SOURCES[key] for key in PROVIDER_SOURCES.get(provider_name, ()))


def attribution_for(sources: Iterable[DataSource]) -> str | None:
    """Join the distinct attribution texts of ``sources``, or None if there are none."""
    return "; ".join(dict.fromkeys(source.attribution for source in sources)) or None


def national_feed_attribution(option: str) -> str | None:
    """Return the attribution for the sources behind one opt-in national feed option."""
    return attribution_for(DATA_SOURCES[key] for key in NATIONAL_FEED_SOURCES.get(option, ()))
