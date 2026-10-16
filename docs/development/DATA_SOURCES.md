# Data source register

Every endpoint the integration calls, who publishes it, the terms that govern reuse, the
attribution to show, and what we decided where the terms are restrictive (#34).

- Runtime attribution and the diagnostics summary come from
  `custom_components/ausnz_disaster_watch/providers/sources.py`. Keep the two in step.
- `tests/test_data_sources.py` fails when a URL in `providers/*.py`, `const.py` or
  `config_flow.py`, or a council `/dashboard/*` path, is missing from this file.
- Terms were checked on **2026-10-16** unless a row says otherwise. Pages marked † returned
  HTTP 403 to `curl` and were read through a search crawler (Exa/Tavily), so the text may
  not be a same-day copy.
- This is a record of what the publishers say, not legal advice.

## Status vocabulary

| Status | Meaning |
| --- | --- |
| `open` | An open licence (CC BY) covers the feed. Attribution names the licence. |
| `restricted` | The terms limit reuse (non-commercial, no derivatives, permission or access request). Kept only until a sanctioned alternative exists; see [Source decisions](#source-decisions). |
| `unverified` | No licence or terms were found for the feed itself. Attribution names the owner only. |
| `replaced` | No longer called by the integration. |

## How the integration polls

- No source needs an API key or account. Requests send `User-Agent: HomeAssistant-AusNZDisasterWatch/1.0`.
- The coordinator refreshes every **300 s**, and every **60 s** while an Emergency Warning or
  Watch and Act is inside the radius. Each refresh fetches each hazard feed once per config entry.
- Transient errors (429, 5xx, network) are retried up to 3 times with 1 s, 2 s backoff.
- Council dashboard payloads are reused within one refresh, and an endpoint a dashboard does
  not have is asked again only after six hours. BoM and MetService CAP documents are cached
  by URL, so only new documents are downloaded.
- Camera snapshots are fetched on demand when a camera entity is viewed (redirects followed).
- The opt-in Open-Meteo forecast features (#38, #39, #40) are off by default and poll on their own
  coordinators, one request per poll and a single attempt (a retry costs quota), retried after
  30 minutes on failure: weather signals hourly, river points every 6 hours (all points in one
  multi-location request), the AI ensemble every 6 hours with WeatherNext 2 at most every 12 hours.
  Adding a river point makes a one-off reanalysis request and, for a point off the river grid, one
  16-location neighbour probe. These requests send
  `User-Agent: AusNZDisasterWatch (+https://github.com/tinkerologie/ha-ausnz-disaster-watch)`.

## Runtime feeds

| Key | Endpoint(s) | Owner | Licence / terms | Attribution shown | Commercial use | Rate limits / access | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `qfd_incidents` | `https://publiccontent-gis-psba-qld-gov-au.s3.amazonaws.com/content/Feeds/BushfireCurrentIncidents/bushfireAlert.json` (`QueenslandHazardProvider.async_fetch_hazards`) | Queensland Fire Department | CC BY 4.0. The dataset page lists this exact file: https://www.data.qld.gov.au/dataset/queensland-fire-and-rescue-current-bushfire-incidents | © State of Queensland (Queensland Fire Department), CC BY 4.0 | Allowed | None published; dataset says it updates every 30 min | `open` |
| `nsw_rfs` | `https://www.rfs.nsw.gov.au/feeds/majorIncidents.json` (`NSWHazardProvider.async_fetch_hazards`); fire danger and total fire bans (#28): `https://www.rfs.nsw.gov.au/_designs/xml/fire-danger-ratings/fire-danger-ratings-v2` (4 days) with fallback `https://www.rfs.nsw.gov.au/feeds/fdrToban.xml` (`FireDangerService`; the feeds page lists `fdrToban.xml`) | NSW Rural Fire Service | CC BY 4.0. The feeds page lists this exact file and gives the attribution: https://www.rfs.nsw.gov.au/news-and-media/stay-up-to-date/feeds. Conflict: the site copyright page (https://www.rfs.nsw.gov.au/about-us/copyright) also says "You may not re-transmit, distribute or commercialise the material without the permission of the RFS". RFS asks republishers to follow its Guideline For Warnings Republishers. | © State of New South Wales (NSW Rural Fire Service), CC BY 4.0. For current information go to www.rfs.nsw.gov.au | Allowed under CC BY (see conflict) | None published | `open` |
| `vic_emergency` | `https://emergency.vic.gov.au/public/osom-geojson.json` (`VictoriaHazardProvider.async_fetch_hazards`) | Emergency Management Victoria (State of Victoria) | https://emergency.vic.gov.au/about-this-site/terms-of-use: "must not reproduce, adapt, modify, communicate to the public or otherwise use any Content (in particular for commercial purposes) without our prior written permission". Covers app and website content and data; no licence specific to OSOM. | VicEmergency, Emergency Management Victoria | Not allowed without permission | None published | `restricted` |
| `wa_emergency` | `https://api.emergency.wa.gov.au/v1/warnings`, `https://api.emergency.wa.gov.au/v1/incidents` (`WAHazardProvider.async_fetch_hazards`), `https://api.emergency.wa.gov.au/v1/fire-danger-ratings` (`async_fetch_fire_danger`), `https://api.emergency.wa.gov.au/v1/total-fire-bans` (`FireDangerService`, total fire bans per LGA, #28) | Department of Fire and Emergency Services (WA) | https://www.emergency.wa.gov.au/about †: copyright CC BY-ND 4.0; terms: "not monitor or copy Emergency WA, or use any software (like bots, scraper tools etc)", with an exemption only for the designated RSS, CAP-AU and SLIP feeds; "no commercial use". The `/v1/*` JSON endpoints are not named as designated feeds. DFES site copyright: https://dfes.wa.gov.au/copyright ("prior written permission"). | © State of Western Australia acting through the Department of Fire and Emergency Services. For current information go to www.emergency.wa.gov.au | Not allowed | None published | `restricted` |
| `sa_eso_cap` | `https://data.eso.sa.gov.au/feeds/prod/cap-au.xml` (`SAHazardProvider.async_fetch_hazards`) | Government of South Australia (CFS, SES) | No dataset or terms cover `cap-au.xml` itself; the data.eso.sa.gov.au root has only a disclaimer. The catalogued CFS incident feeds are CC BY-NC-ND 4.0: https://data.sa.gov.au/data/dataset/south-australian-country-fire-service-current-incidents-rss-feed. CFS website content is CC BY 4.0 but says dataset terms prevail: https://www.cfs.sa.gov.au/home/copyright/ | Government of South Australia (SA Country Fire Service and SA State Emergency Service) | Not allowed (NC) for the catalogued feeds | None published | `restricted` |
| `act_esa` | `https://www.esa.act.gov.au/feeds/currentincidents.xml` (`ACTHazardProvider.async_fetch_hazards`), `https://www.esa.act.gov.au/feeds/firedangerrating.xml` (`FireDangerService`, ACT total fire bans, #28) | ACT Emergency Services Agency | None found. https://esa.act.gov.au/disclaimer has a disclaimer only; https://esa.act.gov.au/copyright shows privacy text. The ACT Government CC BY 4.0 notice (https://www.act.gov.au/copyright) covers act.gov.au, not esa.act.gov.au. | ACT Emergency Services Agency | Unknown | None published | `unverified` |
| `tasalert` | `https://alert.tas.gov.au/data/data.geojson` (`TasmaniaHazardProvider.async_fetch_hazards`) | TasALERT (Tasmanian Government) | https://alert.tas.gov.au/about-app: "You will need permission from the TasALERT team to access the data feeds. Email info@alert.tas.gov.au to request access." Tasmanian Government copyright (http://www.tas.gov.au/stds/codi.htm †): reproduction "for non-commercial purposes only". TFS's own feeds are CC BY 4.0 (https://www.fire.tas.gov.au/Show?pageId=xmlFeedsHome) but that does not cover TasALERT. | TasALERT, Tasmanian Government | Not allowed | Access by request | `restricted` |
| `nt_fire_incidents` | `https://gis-d.nt.gov.au/arcgis/rest/services/Hosted/Fire_Incidents/FeatureServer` layers `0` (Bushfires NT) and `1` (NTFRS) `/query?where=f_status='active'&outFields=*&outSR=4326&f=geojson`, and layer `2` (burnt areas, advice text only) (`NTHazardProvider.async_fetch_hazards`) | Northern Territory Government | The ArcGIS item has no `licenseInfo` or `copyrightText`; its description names the PFES `incidents.json` as its source. NT Government site copyright (https://nt.gov.au/page/copyright-disclaimer-and-privacy †): "No part of this website may be reproduced or reused for any purpose whatsoever", apart from fair dealing or CC-licensed content. data.nt.gov.au has no incidents dataset (only CC BY fire history). | Northern Territory Government (NT Police, Fire and Emergency Services) | Unknown | `maxRecordCount` 2000; the service is reloaded from the PFES data hourly (observed 07:02 and 08:02 ACST on 2026-10-16) | `unverified` |
| `nt_pfes_incidents` | `https://pfes.nt.gov.au/incidentmap/json/incidents.json` | NT Police, Fire and Emergency Services | The file itself: "The format of this file may change without notice. Please do not use, scrape or re-publish this file." | n/a | n/a | n/a | `replaced` by `nt_fire_incidents` (#34) |
| `geonet` | `https://api.geonet.org.nz/quake?MMI=3`, `https://api.geonet.org.nz/volcano/val` (via the `aio_geojson_geonetnz_*` libraries), `https://api.geonet.org.nz/cap/1.2/GPA1.0/feed/atom1.0/quake` (quake CAP alerts) (`NZHazardProvider`) | GeoNet (Earth Sciences New Zealand) | CC BY 3.0 NZ: https://www.geonet.org.nz/policy, https://api.geonet.org.nz/ | GeoNet, Earth Sciences New Zealand, CC BY 3.0 NZ | Allowed | None published; no key | `open` |
| `nzta_roads` | `https://trafficnz.info/service/traffic/rest/4/events/withinbounds` (`NZHazardProvider` road closures) | NZ Transport Agency Waka Kotahi | data.govt.nz lists the dataset licence as "No License Provided"; the NZTA copyright page (https://www.nzta.govt.nz/about-us/about-this-site/copyright/ †) is behind bot protection. Keyless open data. | NZ Transport Agency Waka Kotahi | Unknown | None published; requested for a box around home (~30 kB) | `unverified` |
| `nema_cap` | `https://alerthub.civildefence.govt.nz/atom/pwp` (`NZHazardProvider`) | National Emergency Management Agency (NZ) | CC BY 4.0, attribute to NEMA: https://www.civildefence.govt.nz/about/copyright †. The same page asks that reproduction "for any purpose other than personal or in-house use" be directed to the Director; NEMA's CAP feed announcement invites developers to use the feed. | National Emergency Management Agency (NZ), CC BY 4.0 | Allowed under CC BY | None published | `open` |
| `metservice_cap` | `https://alerts.metservice.com/cap/rss` and the CAP documents it links (`NZHazardProvider`) | Meteorological Service of New Zealand | Feed: "Licensed under Creative Commons BY 4.0." Use is subject to the CAP Code of Practice: https://www.metservice.com/about/common-alerting-protocol † (pass alerts on unmodified, within 10 minutes, acknowledge the issuing authority). Commercial use of open data needs the disclaimer in https://about.metservice.com/our-data-access-policy | MetService, CC BY 4.0 | Allowed with the data access policy disclaimer | Code of Practice R.2: poll at least every 5 min and **not more often than every 2 min** (see decisions) | `open` |
| `bom_wmo` | `https://severeweather.wmo.int/v2/cap-alerts/au-bom-en/rss.xml` and the CAP documents it links (`BoMHazardProvider`) | Bureau of Meteorology, via the WMO Severe Weather Information Centre | WMO: the information is free for reuse by media or other websites, provided it is credited to the issuing national meteorological service (https://severeweather.wmo.int/note.html). BoM default terms: personal or in-organisation use only, "must not supply it to any other person or use it for any commercial purpose" (https://www.bom.gov.au/copyright). BoM RSS terms: personal and non-commercial use, attribution and a link to the BoM website (https://www.bom.gov.au/rss/). Whether BoM terms bind CAP obtained from WMO is not stated. | Australian Government Bureau of Meteorology (www.bom.gov.au), via WMO SWIC | Not allowed under BoM terms | None published | `restricted` |
| `bom_fire_danger` | `https://www.bom.gov.au/fwo/{product}.xml` for the fire danger forecast products (service `WSF`) `IDN10016` (NSW and ACT), `IDV18555` (VIC), `IDQ13016` (QLD), `IDS10070` (SA), `IDW15100` (WA), `IDT13151` (TAS), `IDD10731` (NT) (`FireDangerService`, #28). The bundled district boundaries `data/fire_districts.json` are simplified from BoM `IDM00007` (`ftp://ftp.bom.gov.au/anon/home/adfd/spatial/IDM00007.zip`). | Bureau of Meteorology | BoM copyright (https://www.bom.gov.au/copyright): personal or in-organisation use, no supply to others or commercial use without permission. The product XML links the same page. The ADFD spatial data terms for `IDM00007` were not checked separately. | Australian Government Bureau of Meteorology (www.bom.gov.au) | Not allowed under BoM terms | Products are issued about twice a day; polled at most every 30 min per entry | `restricted` |
| `cfa_fire_bans` | `https://www.cfa.vic.gov.au/cfa/rssfeed/tfbfdrforecast_rss.xml` (`FireDangerService`, VIC total fire bans, #28) | Country Fire Authority | CC BY 4.0. The data.vic dataset lists this exact file: https://discover.data.vic.gov.au/dataset/cfa-data-feeds-for-incidents-total-fire-bans-fire-danger-ratings-and-latest-news | © State of Victoria (Country Fire Authority), CC BY 4.0 | Allowed | None published; polled at most every 30 min | `open` |
| `sa_cfs_fire_danger` | `https://data.eso.sa.gov.au/prod/cfs/criimson/fireDangerRating.xml` (`FireDangerService`, SA total fire bans, #28) | SA Country Fire Service | No dataset covers this file. The CFS feeds next to it in `prod/cfs/criimson/` are catalogued as CC BY-NC-ND 4.0: https://data.sa.gov.au/data/dataset/south-australian-country-fire-service-current-incidents-rss-feed | Government of South Australia (SA Country Fire Service) | Not allowed (NC) for the catalogued feeds | None published; polled at most every 30 min | `restricted` |
| `abs_lga` | `https://geo.abs.gov.au/arcgis/rest/services/ASGS2021/LGA/MapServer/0/query?geometry={lon},{lat}&...` (`FireDangerService`, one point query per location to match Emergency WA's per-LGA total fire bans, #28) | Australian Bureau of Statistics | CC BY 4.0: https://www.abs.gov.au/website-privacy-copyright-and-disclaimer. The service notes that ABS LGAs approximate gazetted boundaries. | © Australian Bureau of Statistics, CC BY 4.0 | Allowed | One request per configured location | `open` |
| `fenz_fire_season` | `https://utility.arcgis.com/usrsvcs/servers/b381ba9bdd4046c2b71a6b1a1e39da78/rest/services/FENZ/MapServer/27/query?geometry={lon},{lat}&...` (fire season zone) and `https://services1.arcgis.com/dcVyucRsXCQAi3GL/arcgis/rest/services/Section_52_Localities_v2_view/FeatureServer/0/query?geometry={lon},{lat}&...` (Section 52 prohibitions) (`FireDangerService`, NZ entries, #28) | Fire and Emergency New Zealand | No licence found for the layers; the services carry no licence or copyright text and https://www.fireandemergency.nz/about-us/copyright/ states none for data. | Fire and Emergency New Zealand | Unknown | Polled at most every 30 min | `unverified` |
| `ga_earthquakes` | `https://earthquakes.ga.gov.au/geoserver/earthquakes/wfs?service=WFS&request=getfeature&typeNames=earthquakes:earthquakes_seven_days&outputFormat=application/json` (`GAEarthquakeProvider.async_fetch_hazards`, opt-in, #23); hazards link to `https://earthquakes.ga.gov.au/event/{event_id}` | Geoscience Australia | CC BY 4.0: "All material on this website is licensed under the Creative Commons Attribution 4.0 International Licence" (https://www.ga.gov.au/copyright). The WFS capabilities list `Fees: NONE`, `AccessConstraints: NONE`. | © Commonwealth of Australia (Geoscience Australia), CC BY 4.0 | Allowed | None published; no key | `open` |
| `open_meteo_forecast` | `https://api.open-meteo.com/v1/forecast` (`OpenMeteoClient.async_get_forecast`, weather hazard signals #39) | Open-Meteo | CC BY 4.0 (https://open-meteo.com/en/licence; credit "Weather data by Open-Meteo.com" with a link). Free API terms (https://open-meteo.com/en/terms): non-commercial use only. Best-match model; `lightning_potential` is not used (empty for AU/NZ). | Weather data by Open-Meteo.com, CC BY 4.0 | Not allowed on the free API (commercial plan needed) | Under 10,000 calls a day, 5,000 an hour, 600 a minute per IP; large requests count as several calls; no key | `open` |
| `open_meteo_flood` | `https://flood-api.open-meteo.com/v1/flood` (`OpenMeteoClient.async_get_river_forecasts`, `async_get_river_history`, river flood forecast #38) | Open-Meteo, with GloFAS v4 data from the Copernicus Emergency Management Service | CC BY 4.0 (https://open-meteo.com/en/licence; credit "Weather data by Open-Meteo.com" with a link). Free API terms (https://open-meteo.com/en/terms): non-commercial use only. GloFAS is listed on the Open-Meteo licence page. | Flood data by Open-Meteo.com (GloFAS), CC BY 4.0 | Not allowed on the free API | As `open_meteo_forecast`; each location in a multi-location request counts | `open` |
| `ecmwf_aifs` | `https://ensemble-api.open-meteo.com/v1/ensemble` with `models=ecmwf_aifs025_ensemble` (`OpenMeteoClient.async_get_ensemble`, AI rain outlook #40) | ECMWF, served by Open-Meteo | ECMWF open data, CC BY 4.0 (https://www.ecmwf.int/en/forecasts/datasets/open-data); Open-Meteo free API terms as above | ECMWF AIFS, CC BY 4.0 (with the Open-Meteo credit) | Not allowed on the free Open-Meteo API | As `open_meteo_forecast`; ensemble requests count per member set | `open` |
| `google_weathernext2` | same endpoint with `models=google_weathernext2_ensemble` (AI rain outlook #40, its own toggle, off by default) | Google DeepMind, served by Open-Meteo | Not verified. Open-Meteo's page (https://open-meteo.com/en/docs/google-weathernext-api) states no licence. Google's "GDM Real-Time Weather Forecasting Experimental Data Terms of Use" limit real-time data to internal use; data older than 1 hour is CC BY 4.0. Whether these terms carry through to Open-Meteo is not confirmed; separately removable. | Google WeatherNext 2 | Unknown | As `ecmwf_aifs`; fetched at most every 12 hours | `unverified` |

## Council disaster dashboards (Guardian IMS)

Key `guardian_ims`, status `restricted`. QLD and NSW read JSON from the configured council
dashboard (`{base_url}/dashboard/...`). The dashboards are built by QIT Plus ("Dashboard
Powered By QIT Plus"); no QIT Plus terms are published and the dashboard disclaimer is empty.
Terms are the council's website terms, and differ by council:

- City of Moreton Bay (https://www.moretonbay.qld.gov.au/Council/Governance/Copyright †): CC BY 4.0, excluding third-party material; "© Moreton Bay City Council".
- Hawkesbury City Council (https://www.hawkesbury.nsw.gov.au/footer-links/disclaimer †): "personal, in-house or non-commercial use. You may not re-transmit, distribute or commercialise the material without the permission".
- Other councils: not checked.

Attribution shown: "Local council disaster dashboard (Guardian IMS)".

Endpoints are fetched by `GuardianDashboard.fetch` in `providers/guardian_ims.py` as
`{base_url}/dashboard/<endpoint>`; not every dashboard has every endpoint.

| Endpoint | Used for | Content |
| --- | --- | --- |
| `/dashboard/getTemplateWidgets` | Station IDs for observations and air quality | Dashboard configuration (council-only) |
| `/dashboard/tmrRoadData` | QLD hazards, road closures | Re-served QLDTraffic events (upstream agency: Transport and Main Roads) |
| `/dashboard/imsBulletin` | QLD hazards, news | Council bulletins (council-only) |
| `/dashboard/ergonOutages` | Power outages | Re-served Ergon Energy outages (upstream) |
| `/dashboard/energexOutages` | Power outages | Re-served Energex outages (upstream) |
| `/dashboard/imsRoad` | Road closures | Council road closures (council-only) |
| `/dashboard/moretonRoadClosures` | Road closures | Moreton Bay road closures (council-only) |
| `/dashboard/imsEvac` | Relief facilities | Council evacuation centres, refuges, sandbag points (council-only) |
| `/dashboard/sandbagStations` | Relief facilities | Council sandbag stations (council-only) |
| `/dashboard/moretonEvacs` | Relief facilities | Moreton Bay evacuation centres (council-only) |
| `/dashboard/getSurfaceObservation?ObsId=...` | Weather observations | Re-served BoM surface observations (upstream) |
| `/dashboard/getWeatherStationsData` | Weather observations | Council weather stations (council-only) |
| `/dashboard/Currtemp` | Weather observations | Council weather stations (council-only) |
| `/dashboard/airQuality?stationIds=...` | Air quality | Re-served Queensland Government air monitoring (upstream) |
| `/dashboard/fireDangerRating` | Fire danger | Re-served AFDRS ratings (upstream) |
| `/dashboard/bom` | Weather warnings | Re-served BoM warning summary (upstream) |
| `/dashboard/getCameras` | Cameras | Council flood and traffic cameras; `image_url` points at council-hosted images (e.g. `camera-custom-image.s3-ap-southeast-2.amazonaws.com` for Moreton Bay), fetched on demand |

Council base URLs the integration offers or links to (presets in `const.py`, the default in
`config_flow.py`, the host aliases in `guardian_ims.py`, and the "nearby councils" links in
`qld.py` and `nsw.py`; links are never polled):

- QLD presets: https://disaster.moretonbay.qld.gov.au, https://disaster.noosa.qld.gov.au, https://disaster.cairns.qld.gov.au, https://disaster.townsville.qld.gov.au, https://disaster.frasercoast.qld.gov.au, https://disaster.bundaberg.qld.gov.au, https://disaster.ipswich.qld.gov.au, https://disaster.logan.qld.gov.au, https://dashboard.goldcoast.qld.gov.au, https://dashboard.redland.qld.gov.au (old hosts `disaster.goldcoast`, `dashboard.cityofgoldcoast.com.au` and `disaster.redland` are aliased to these)
- QLD links: https://disasterhub.sunshinecoast.qld.gov.au (a web app, not Guardian IMS), https://www.brisbane.qld.gov.au/community-support-and-safety/natural-disasters-and-emergencies/emergency-dashboard, https://disaster.somerset.qld.gov.au
- NSW: https://disaster.hawkesbury.nsw.gov.au, https://emergency.bmcc.nsw.gov.au, https://emergency.ballina.nsw.gov.au, https://emergency.byron.nsw.gov.au, https://emergency.northernbeaches.nsw.gov.au

## Informational links

Links put into entity attributes (`web_url`, `link`). The integration does not fetch them.

- QFD: https://www.fire.qld.gov.au/Current-Incidents
- QLDTraffic: https://qldtraffic.qld.gov.au (road events re-served by council dashboards link here)
- BoM: http://www.bom.gov.au/qld/warnings/, https://www.bom.gov.au/australia/warnings (BoM items prefer the CAP `web` link; `http://www.bom.gov.au` links are upgraded to `https://www.bom.gov.au`)
- NSW RFS: https://www.rfs.nsw.gov.au/fire-information/fires-near-me
- VicEmergency: https://emergency.vic.gov.au/respond/#!/{path}/moreinfo
- Emergency WA: https://www.emergency.wa.gov.au, https://www.emergency.wa.gov.au/#/warning/{item_id}
- SA CFS: https://www.cfs.sa.gov.au
- ACT ESA: https://esa.act.gov.au
- TasALERT: https://alert.tas.gov.au/
- NT: https://securent.nt.gov.au/alerts
- GeoNet: https://www.geonet.org.nz/earthquake/{public_id}, https://www.geonet.org.nz/volcano/{volcano_id}
- NEMA: https://www.civildefence.govt.nz
- MetService: https://www.metservice.com/warnings/home

## Source decisions

Dated 2026-10-16 (#34).

- **NT: replaced.** The PFES `incidents.json` file asks not to be used, scraped or
  re-published. The integration now reads the NT Government `Hosted/Fire_Incidents`
  FeatureServer, which the NT Government publishes without a key. Its licence is
  `unverified`, and it is refreshed from the PFES data hourly, so NT incidents can lag the
  PFES map by up to an hour. Follow-up: ask NT PFES / NT Government to confirm reuse of the
  service (see #14).
- **VIC OSOM: kept, flagged.** EMV terms require prior written permission. The CFA feeds on
  data.vic.gov.au are CC BY 4.0, but they cover CFA only, not the other Victorian agencies
  in OSOM, so switching would remove most VIC coverage. Follow-up: the maintainer asks EMV
  for written permission; if refused, move to the CFA feeds.
- **TasALERT: kept, flagged.** Feed access is by permission. The integration reads
  `data.geojson` (#14). Follow-up: the maintainer requests access (info@alert.tas.gov.au).
- **SA: kept, flagged.** The catalogued CFS feeds are CC BY-NC-ND; nothing covers
  `cap-au.xml`. Follow-up: ask SA ESO which terms apply to the CAP-AU feed.
- **WA: kept, flagged.** The terms only exempt the designated RSS, CAP-AU and SLIP feeds from
  the no-copying clause. Sanctioned alternatives exist for incidents and warnings
  (`/v1/rss/incidents`, `/v1/rss/warnings`, both respond; `/v1/cap/warnings` returned 403),
  but not for fire danger ratings. Switching is a parser rewrite that overlaps the open WA
  fixes in #14, so it is a follow-up for after those merge.
- **BoM: kept, flagged.** WMO allows reuse crediting the issuing service; BoM's own terms are
  non-commercial and want a link to the BoM website. Attribution names BoM and links
  www.bom.gov.au, and warnings keep their BoM `web_url`.
- **Guardian IMS: kept, flagged.** Council-only paths stay. Re-served upstream paths
  (`tmrRoadData`, `ergonOutages`, `energexOutages`, `getSurfaceObservation`, `airQuality`,
  `fireDangerRating`, `bom`)
  are candidates for replacement by the upstream agency feeds (roads and fire danger work).
- **QLDTraffic webcams: removed upstream of this change.** The hard-coded
  `131940.qld.gov.au` webcam images (personal, non-commercial terms at
  https://qldtraffic.qld.gov.au/more/Disclaimer/index.html; the URLs had started redirecting
  to the QLDTraffic home page) were replaced by the dashboard's own `getCameras` list (#25).
- **MetService polling: open.** The CAP Code of Practice asks for polls no more often than
  every 2 minutes; the coordinator's 60 s threat interval breaks that for NZ entries while a
  threat is active. Follow-up: throttle the MetService RSS to 120 s or more.

## Permission requests

The maintainer makes these contacts; record only replies the maintainer supplies.

| Publisher | Request | Contact | Sent | Reply |
| --- | --- | --- | --- | --- |
| Emergency Management Victoria | Written permission for OSOM reuse | via emergency.vic.gov.au | not yet | — |
| TasALERT | Feed access | info@alert.tas.gov.au | not yet | — |
| NT PFES / NT Government | Confirm reuse of `Fire_Incidents` | — | not yet | — |
| SA ESO | Terms for `cap-au.xml` | — | not yet | — |
| DFES (WA) | Use of `/v1/*` JSON or SLIP | statepublicinfo@dfes.wa.gov.au | not yet | — |
| Bureau of Meteorology | Terms for CAP warnings via WMO | — | not yet | — |
| NSW SES / HazardWatch | Feed reuse | — | not yet | — |

## Proposed sources with restrictive terms

Not used. Do not add them without permission.

- HazardWatch (NSW SES), https://www.hazardwatch.gov.au/terms: "You will not reproduce information or data ... except where such reproduction is for Your own personal non-commercial use".
- MetService `publicData/webdata/*`, https://about.metservice.com/web-terms-of-use: no scraping or automation. Use the CC BY CAP feed instead.
- BoM `api.weather.bom.gov.au`: the API response says "You must not use, copy or share it."
- NIWA fireweather: terms forbid redistribution (from the issue; not rechecked).
- Demonz council dashboards: "Unauthorised use is not permitted" (from the issue; not rechecked).

## Sources in open pull requests

None. A PR that adds a source must add it to [Runtime feeds](#runtime-feeds) and
`providers/sources.py`; `tests/test_data_sources.py` fails until it does.

## Candidate open sources

Not used yet; licences as reported in #34 and its comments, to be rechecked when a source is added.

- Live Traffic NSW (CC BY), QLDTraffic GeoJSON API (CC BY 4.0, key), Main Roads WA (CC BY 4.0), Traffic SA (CC BY), VIC DTP (CC BY 4.0, key), DEA Hotspots (CC BY 4.0), Brisbane open data (CC BY 4.0), CFA feeds (CC BY 4.0, CFA only), TFS feeds (CC BY 4.0 with display conditions).
- MET Norway (https://api.met.no/doc/TermsOfService): NLOD 2.0 and CC BY 4.0, credit "Data from MET Norway"; requires an identifying User-Agent that does not start with "HomeAssistant".

## Out of scope

- XML namespace URIs (`http://www.w3.org/2005/Atom`, `http://www.georss.org/georss`, `http://purl.org/dc/elements/1.1/`): identifiers, never fetched.
- URLs in `script/`, `.github/workflows/`, `config/`, `tests/` and the frontend build: development tooling, test fixtures and project links, not data sources.
