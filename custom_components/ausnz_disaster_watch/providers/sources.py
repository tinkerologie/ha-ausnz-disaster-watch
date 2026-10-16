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
    DataSource(
        key="bom_wmo",
        owner="Australian Government Bureau of Meteorology (via WMO Severe Weather Information Centre)",
        attribution="Australian Government Bureau of Meteorology (www.bom.gov.au), via WMO SWIC",
        licence="BoM: personal and non-commercial use; WMO SWIC: free reuse crediting the issuing service",
        terms_url="https://www.bom.gov.au/copyright",
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
)

DATA_SOURCES: dict[str, DataSource] = {source.key: source for source in _SOURCES}

# Provider class name -> register keys of the sources it reads
PROVIDER_SOURCES: dict[str, tuple[str, ...]] = {
    "QueenslandHazardProvider": ("qfd_incidents", "guardian_ims"),
    "NSWHazardProvider": ("nsw_rfs", "guardian_ims"),
    "VictoriaHazardProvider": ("vic_emergency",),
    "WAHazardProvider": ("wa_emergency",),
    "SAHazardProvider": ("sa_eso_cap",),
    "ACTHazardProvider": ("act_esa",),
    "TasmaniaHazardProvider": ("tasalert",),
    "NTHazardProvider": ("nt_fire_incidents",),
    "NZHazardProvider": ("geonet", "nema_cap", "metservice_cap", "nzta_roads"),
    "BoMHazardProvider": ("bom_wmo",),
}


# Forecast feature -> register keys (these are not hazard providers)
FORECAST_SOURCES: dict[str, tuple[str, ...]] = {
    "weather_signals": ("open_meteo_forecast",),
    "river_forecast": ("open_meteo_flood",),
    "ai_ensemble": ("open_meteo_forecast", "ecmwf_aifs"),
    "ai_weathernext": ("google_weathernext2",),
}


def sources_for_forecast(*features: str) -> tuple[DataSource, ...]:
    """Return the register entries for forecast features, in order."""
    return tuple(DATA_SOURCES[key] for feature in features for key in FORECAST_SOURCES[feature])


def sources_for_provider(provider_name: str) -> tuple[DataSource, ...]:
    """Return the register entries for a provider class name (none for unknown providers)."""
    return tuple(DATA_SOURCES[key] for key in PROVIDER_SOURCES.get(provider_name, ()))


def attribution_for(sources: Iterable[DataSource]) -> str | None:
    """Join the distinct attribution texts of ``sources``, or None if there are none."""
    return "; ".join(dict.fromkeys(source.attribution for source in sources)) or None
