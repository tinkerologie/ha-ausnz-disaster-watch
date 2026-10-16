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

- Only the optional VIC road feed (`dtp_vic_roads`) needs an API key (a free DTP key, off unless the user enters one). Requests send `User-Agent: HomeAssistant-AusNZDisasterWatch/1.0`.
- Statewide road feeds (#29) are fetched at most every **4 minutes** whatever the coordinator interval, and keep their last good items for up to 30 minutes when a source is down.
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
| `qfd_warning_areas` | `https://services1.arcgis.com/vkTwD8kHw2woKBqV/ArcGIS/rest/services/OCSWarnings_PublicView/FeatureServer/0` `/query?where=1=1&outFields=UniqueID,WarningTitle,WarningLevel,WarningArea,CallToAction,MasterIncidentNum,ModifiedDate&outSR=4326&f=geojson` (`QueenslandHazardProvider.async_fetch_hazards`, #30) | Queensland Fire Department (item "QFES OCS Warnings Areas Public View", owner `qfes_FIMS`) | The ArcGIS item (https://www.arcgis.com/home/item.html?id=7da8fbcdd23541c4ab0464a685e2b3de) is public; its `licenseInfo` is a disclaimer only and its credit is "State of Queensland (Queensland Fire and Emergency Services)". No licence. | State of Queensland (Queensland Fire and Emergency Services) | Unknown | `maxRecordCount` 2000 | `unverified` |
| `qps_warning_areas` | `https://services-ap1.arcgis.com/4z1c8UDtmlbV0cw9/ArcGIS/rest/services/Severe_Weather_Flood_Cyclone_Area_Public_View/FeatureServer/0` `/query?where=1=1&outFields=UniqueID,WarningTitle,WarningLevel,last_edited_date&outSR=4326&f=geojson` (`QueenslandHazardProvider.async_fetch_hazards`, #30) | Queensland Police Service (owner `QPSAdmin`) | The ArcGIS item (https://www.arcgis.com/home/item.html?id=a858cd92be2d48479ae5a30d8cfce10c) is public with no licence or credit. The layer also has `last_edited_user` (staff email addresses), which is never requested; the matching point layer is not used. | Queensland Police Service | Unknown | `maxRecordCount` 2000 | `unverified` |
| `nsw_rfs` | `https://www.rfs.nsw.gov.au/feeds/majorIncidents.json` (`NSWHazardProvider.async_fetch_hazards`); fire danger and total fire bans (#28): `https://www.rfs.nsw.gov.au/_designs/xml/fire-danger-ratings/fire-danger-ratings-v2` (4 days) with fallback `https://www.rfs.nsw.gov.au/feeds/fdrToban.xml` (`FireDangerService`; the feeds page lists `fdrToban.xml`) | NSW Rural Fire Service | CC BY 4.0. The feeds page lists this exact file and gives the attribution: https://www.rfs.nsw.gov.au/news-and-media/stay-up-to-date/feeds. Conflict: the site copyright page (https://www.rfs.nsw.gov.au/about-us/copyright) also says "You may not re-transmit, distribute or commercialise the material without the permission of the RFS". RFS asks republishers to follow its Guideline For Warnings Republishers. | © State of New South Wales (NSW Rural Fire Service), CC BY 4.0. For current information go to www.rfs.nsw.gov.au | Allowed under CC BY (see conflict) | None published | `open` |
| `vic_emergency` | `https://emergency.vic.gov.au/public/osom-geojson.json` (`VictoriaHazardProvider.async_fetch_hazards`) | Emergency Management Victoria (State of Victoria) | https://emergency.vic.gov.au/about-this-site/terms-of-use: "must not reproduce, adapt, modify, communicate to the public or otherwise use any Content (in particular for commercial purposes) without our prior written permission". Covers app and website content and data; no licence specific to OSOM. | VicEmergency, Emergency Management Victoria | Not allowed without permission | None published | `restricted` |
| `wa_emergency` | `https://api.emergency.wa.gov.au/v1/rss/warnings`, `https://api.emergency.wa.gov.au/v1/rss/incidents` (`WAHazardProvider.async_fetch_hazards`, designated RSS feeds since #61), `https://api.emergency.wa.gov.au/v1/fire-danger-ratings` (`async_fetch_fire_danger`) and `https://api.emergency.wa.gov.au/v1/total-fire-bans` (`FireDangerService`, total fire bans per LGA, #28), **not** designated feeds | Department of Fire and Emergency Services (WA) | https://www.emergency.wa.gov.au/about †: copyright CC BY-ND 4.0; terms: "not monitor or copy Emergency WA, or use any software (like bots, scraper tools etc)", with an exemption only for the designated RSS, CAP-AU and SLIP feeds; "no commercial use". The RSS feeds are designated; `/v1/fire-danger-ratings` and `/v1/total-fire-bans` are not, and no designated feed publishes district ratings or per-LGA bans (see decisions). CC BY-ND: warning text is passed on unaltered. DFES site copyright: https://dfes.wa.gov.au/copyright ("prior written permission"). | © State of Western Australia acting through the Department of Fire and Emergency Services. For current information go to www.emergency.wa.gov.au | Not allowed | RSS `<ttl>1</ttl>` (minutes); no limit published. The CAP-AU path `/v1/cap/warnings` returned 403 on 2026-10-16 | `restricted` (FDR and TFB endpoints) |
| `sa_eso_cap` | `https://data.eso.sa.gov.au/feeds/prod/cap-au.xml` (`SAHazardProvider.async_fetch_hazards`) | Government of South Australia (CFS, SES) | No dataset or terms cover `cap-au.xml` itself; the data.eso.sa.gov.au root has only a disclaimer. The catalogued CFS incident feeds are CC BY-NC-ND 4.0: https://data.sa.gov.au/data/dataset/south-australian-country-fire-service-current-incidents-rss-feed. CFS website content is CC BY 4.0 but says dataset terms prevail: https://www.cfs.sa.gov.au/home/copyright/ | Government of South Australia (SA Country Fire Service and SA State Emergency Service) | Not allowed (NC) for the catalogued feeds | None published | `restricted` |
| `sa_ses_warnings` | `https://ses.geohub.sa.gov.au/server/rest/services/SAM_PROD_Services/SAM_Warnings_Public_Live/FeatureServer/0` `/query?where=status='Published'&outFields=objectid,documentid,alertname,risk,category,datetimeissued,datetimeexpires,shortlocation,locationsimpacted,calltoaction,link&outSR=4326&f=geojson` (`SAHazardProvider.async_fetch_hazards`, #30) | SA State Emergency Service | The ArcGIS item (https://ses.geohub.sa.gov.au/portal/home/item.html?id=0bc5049da77b4035b67f8ade3f20a034) has licence "Public Use" and credit "SA SES Mapping team"; its description says it serves "external agencies" and web mapping. No licence terms. The layer's editor fields (`created_user`, `last_edited_user`, `adfs_user`) are never requested. | SA State Emergency Service | Unknown | `maxRecordCount` 1000 | `unverified` |
| `act_esa` | `https://www.esa.act.gov.au/feeds/currentincidents.xml` (`ACTHazardProvider.async_fetch_hazards`), `https://www.esa.act.gov.au/feeds/firedangerrating.xml` (`FireDangerService`, ACT total fire bans, #28) | ACT Emergency Services Agency | None found. https://esa.act.gov.au/disclaimer has a disclaimer only; https://esa.act.gov.au/copyright shows privacy text. The ACT Government CC BY 4.0 notice (https://www.act.gov.au/copyright) covers act.gov.au, not esa.act.gov.au. | ACT Emergency Services Agency | Unknown | None published | `unverified` |
| `tasalert` | `https://alert.tas.gov.au/data/data.geojson` (`TasmaniaHazardProvider.async_fetch_hazards`), `https://alert.tas.gov.au/proxy/road-closures` (`TasmaniaRoadProvider`, road closures, #29) | TasALERT (Tasmanian Government) | https://alert.tas.gov.au/about-app: "You will need permission from the TasALERT team to access the data feeds. Email info@alert.tas.gov.au to request access." Tasmanian Government copyright (http://www.tas.gov.au/stds/codi.htm †): reproduction "for non-commercial purposes only". TFS's own feeds are CC BY 4.0 (https://www.fire.tas.gov.au/Show?pageId=xmlFeedsHome) but that does not cover TasALERT. | TasALERT, Tasmanian Government | Not allowed | Access by request | `restricted` |
| `nt_fire_incidents` | `https://gis-d.nt.gov.au/arcgis/rest/services/Hosted/Fire_Incidents/FeatureServer` layers `0` (Bushfires NT) and `1` (NTFRS) `/query?where=f_status='active'&outFields=*&outSR=4326&f=geojson`, and layer `2` (burnt areas, advice text only) (`NTHazardProvider.async_fetch_hazards`) | Northern Territory Government | The ArcGIS item has no `licenseInfo` or `copyrightText`; its description names the PFES `incidents.json` as its source. NT Government site copyright (https://nt.gov.au/page/copyright-disclaimer-and-privacy †): "No part of this website may be reproduced or reused for any purpose whatsoever", apart from fair dealing or CC-licensed content. data.nt.gov.au has no incidents dataset (only CC BY fire history). | Northern Territory Government (NT Police, Fire and Emergency Services) | Unknown | `maxRecordCount` 2000; the service is reloaded from the PFES data hourly (observed 07:02 and 08:02 ACST on 2026-10-16) | `unverified` |
| `nt_pfes_incidents` | `https://pfes.nt.gov.au/incidentmap/json/incidents.json` | NT Police, Fire and Emergency Services | The file itself: "The format of this file may change without notice. Please do not use, scrape or re-publish this file." | n/a | n/a | n/a | `replaced` by `nt_fire_incidents` (#34) |
| `geonet` | `https://api.geonet.org.nz/quake?MMI=3`, `https://api.geonet.org.nz/volcano/val` (via the `aio_geojson_geonetnz_*` libraries), `https://api.geonet.org.nz/cap/1.2/GPA1.0/feed/atom1.0/quake` (quake CAP alerts) (`NZHazardProvider`) | GeoNet (Earth Sciences New Zealand) | CC BY 3.0 NZ: https://www.geonet.org.nz/policy, https://api.geonet.org.nz/ | GeoNet, Earth Sciences New Zealand, CC BY 3.0 NZ | Allowed | None published; no key | `open` |
| `nzta_roads` | `https://trafficnz.info/service/traffic/rest/4/events/withinbounds` (`NZHazardProvider` road closures) | NZ Transport Agency Waka Kotahi | data.govt.nz lists the dataset licence as "No License Provided"; the NZTA copyright page (https://www.nzta.govt.nz/about-us/about-this-site/copyright/ †) is behind bot protection. Keyless open data. | NZ Transport Agency Waka Kotahi | Unknown | None published; requested for a box around home (~30 kB) | `unverified` |
| `nema_cap` | `https://alerthub.civildefence.govt.nz/atom/pwp` (`NZHazardProvider`) | National Emergency Management Agency (NZ) | CC BY 4.0, attribute to NEMA: https://www.civildefence.govt.nz/about/copyright †. The same page asks that reproduction "for any purpose other than personal or in-house use" be directed to the Director; NEMA's CAP feed announcement invites developers to use the feed. | National Emergency Management Agency (NZ), CC BY 4.0 | Allowed under CC BY | None published | `open` |
| `metservice_cap` | `https://alerts.metservice.com/cap/rss` and the CAP documents it links (`NZHazardProvider`) | Meteorological Service of New Zealand | Feed: "Licensed under Creative Commons BY 4.0." Use is subject to the CAP Code of Practice: https://www.metservice.com/about/common-alerting-protocol † (pass alerts on unmodified, within 10 minutes, acknowledge the issuing authority). Commercial use of open data needs the disclaimer in https://about.metservice.com/our-data-access-policy | MetService, CC BY 4.0 | Allowed with the data access policy disclaimer | Code of Practice R.2: poll at least every 5 min and **not more often than every 2 min** (see decisions) | `open` |
| `livetraffic_nsw` | `https://www.livetraffic.com/traffic/hazards/{incident,flood,fire,alpine}.json` and `/regional/lga-incidents.json`; `roadwork.json` and `majorevent.json` only with *Include planned roadworks and events* (`NSWRoadProvider`) | Transport for NSW | CC BY: https://opendata.transport.nsw.gov.au/dataset/live-traffic-hazards (catalogue `license_id` `cc-by`); each feed's `rights` names Transport for NSW and links that dataset. The catalogue's API downloads need a login; these keyless files are the ones Live Traffic NSW serves. | © Transport for NSW (Live Traffic NSW), CC BY 4.0 | Allowed | `Cache-Control: max-age=30`; none published | `open` |
| `qldtraffic_events` | `https://data.qldtraffic.qld.gov.au/events_v2.geojson` (`QueenslandRoadProvider`) | Department of Transport and Main Roads (QLDTraffic) | CC BY 4.0: https://www.data.qld.gov.au/dataset/131940-traffic-and-travel-information-geojson-api (catalogue `CC-BY-4.0`). **This keyless path is not in the API documentation**; the documented `api.qldtraffic.qld.gov.au/v2/events` needs a key. The feed's `rights` say copyright belongs to TMR or the council named in each event's `provided_by`. | © State of Queensland (Department of Transport and Main Roads), QLDTraffic, CC BY 4.0 | Allowed | None published; ~440 KB gzip per fetch | `open` |
| `dtp_vic_roads` | `https://api.opendata.transport.vic.gov.au/api/opendata/roads/disruptions/unplanned/v3` (`VictoriaRoadProvider`, only with a key) | Department of Transport and Planning (Victoria) | CC BY 4.0: https://opendata.transport.vic.gov.au/dataset/unplanned-disruptions-road (catalogue `cc-by`). Needs a free key in a `KeyID` header (401 without it). | © State of Victoria (Department of Transport and Planning), CC BY 4.0 | Allowed | 10 calls/minute (dataset page); free registration | `open` |
| `traffic_sa` | `https://maps.sa.gov.au/arcgis/rest/services/DPTIExtTransport/TrafficSAOpenData/MapServer` layers `0` (incidents; roadworks only with the option) and `1` (closures), queried with the radius box (`SARoadProvider`) | Department for Infrastructure and Transport (South Australia) | CC BY: https://data.sa.gov.au/data/dataset/roadworks-and-incidents-real-time-information (catalogue `cc-by`; data.gov.au lists CC BY 3.0 AU) | © Government of South Australia (Department for Infrastructure and Transport), Traffic SA, CC BY | Allowed | `maxRecordCount` 1000; paged | `open` |
| `mrwa_webeoc` | `https://services2.arcgis.com/cHGEnmsJ165IBJRM/arcgis/rest/services/WebEocFeatureLayerViewPRD/FeatureServer` layers `1` (incidents) and `4` (closures) with `publishExt='Yes'`, `2` (roadworks) and `0` (events) only with the option, queried with the radius box (`WARoadProvider`) | Main Roads Western Australia | CC BY 4.0: https://catalogue.data.wa.gov.au/dataset/mrwa-webeoc-road-closures and `mrwa-webeoc-road-incidents` (catalogue `cc-by`). Attribution names the Commissioner of Main Roads. | © Commissioner of Main Roads Western Australia, CC BY 4.0 | Allowed | `maxRecordCount` 2000 | `open` |
| `nt_road_report` | `https://roadreport.nt.gov.au/api/Obstruction/GetAll` (`NTRoadProvider`) | Northern Territory Government (Department of Logistics and Infrastructure) | None found. https://roadreport.nt.gov.au/copyright and `/disclaimer` are script-rendered shells with no text for `curl`; no dataset on data.nt.gov.au. The NT Government site copyright (see `nt_fire_incidents`) is restrictive but covers nt.gov.au pages. | NT Road Report, Northern Territory Government | Unknown | None published | `unverified` |
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
| `river_qld_wmip` | `https://water-monitoring.information.qld.gov.au/cgi/webservice.exe` (Kisters Hydstra JSON: `get_sites_by_datasource`, `get_db_info`, `get_ts_traces`; `rivers.py`, opt-in river gauges #31) | Queensland Government (Department of Local Government, Water and Volunteers) | CC BY 4.0: every response carries `"licence":"CC_40_BY"` and the disclaimer https://www.qld.gov.au/legal/disclaimer | © State of Queensland, Water Monitoring Information Portal, CC BY 4.0 | Allowed | None published; the selected gauges are polled every 15 min in one request, and the site list is cached for 24 h | `open` |
| `river_waternsw` | `https://realtimedata.waternsw.com.au/cgi/webservice.exe` (Kisters Hydstra JSON, datasource `CP`; `rivers.py`, #31) | WaterNSW | CC BY: data.gov.au and SEED list the WaterNSW real-time water datasets as CC BY, but the version differs between listings (3.0 or 4.0): https://data.gov.au/data/dataset/nsw-real-time-water. The registered WaterNSW API is a separate, keyed service and is not used | © State Government of NSW and WaterNSW, CC BY | Allowed under CC BY | As `river_qld_wmip` | `open` |
| `river_hbrc_hilltop` | `https://data.hbrc.govt.nz/Envirodata/EMAR.hts` (Hilltop `SiteList`/`GetData`, measurement `Stage`; `rivers.py`, #31) | Hawke's Bay Regional Council | "Data on this site is licensed under a Creative Commons Attribution 3.0 or 4.0 New Zealand License": https://www.hbrc.govt.nz/our-council/open-data/ | Hawke's Bay Regional Council, CC BY | Allowed | As `river_qld_wmip`; one `GetData` request per selected gauge | `open` |
| `river_nz_hilltop` | `https://hilltop.gw.govt.nz/Data.hts`, `https://hilltopserver.horizons.govt.nz/data.hts`, `https://envdata.tasman.govt.nz/data.hts`, `https://hilltop.nrc.govt.nz/Data.hts`, `https://hilltop.wcrc.govt.nz/Data.hts`, `https://extranet.trc.govt.nz/getdata/merged.hts`, `https://hydro.marlborough.govt.nz/data.hts` (Hilltop, measurement `Stage`; `rivers.py`, #31) | Greater Wellington, Horizons, Tasman, Northland, West Coast, Taranaki and Marlborough councils | None found for the Hilltop servers themselves. They are public and keyless, and several councils publish other datasets as CC BY 4.0 on data.govt.nz | The council's name | Unverified | As `river_hbrc_hilltop` | `unverified` |

Opt-in national and regional feeds (#37). All are off by default; each is enabled by its own option. Checked 2026-10-16.

| Key | Endpoint(s) | Owner | Licence / terms | Attribution shown | Commercial use | Rate limits / access | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `bom_ftp` | `ftp://ftp.bom.gov.au/anon/gen/fwo/`: JATWC tsunami `IDY680nn` CAP (`NLST IDY68*` each poll, only matching `*cap.xml` files downloaded), heatwave `IDx21013.cap.xml` / ACT `IDN21014.cap.xml` (hourly), UV forecast `IDZ00107`-`IDZ00113.xml` (hourly) (`NationalHazardProvider` via `providers/bom_ftp.py`) | Bureau of Meteorology (JATWC with Geoscience Australia) | BoM default terms: personal or in-organisation use, no supply to others, no commercial use (https://www.bom.gov.au/copyright). Anonymous FTP is BoM's documented product channel. | Australian Government Bureau of Meteorology (www.bom.gov.au) | Not allowed under BoM terms | Anonymous FTP; one connection per refresh, listing by pattern only | `restricted` |
| `ptwc` | `https://www.tsunami.gov/events/xml/PHEBAtom.xml` and the CAP documents its entries link (NZ entries only) | NOAA NWS Pacific Tsunami Warning Center | US Government work, public domain; credit NOAA, no endorsement implied (https://www.weather.gov/disclaimer). International guidance, not an official NZ warning. | NOAA Pacific Tsunami Warning Center (US Government work, public domain; no licence needed) | Allowed | None published | `open` |
| `dea_hotspots` | `https://hotspots.dea.ga.gov.au/geoserver/public/wfs` `GetFeature` on `public:hotspots_three_days`, always with `hours_since_hotspot<24`, `confidence>=50`, `BBOX(location,…,'CRS:84')` around the radius and a `count` cap (never `recent-hotspots.json`) | Geoscience Australia (Digital Earth Australia) | CC BY 4.0 (https://www.ga.gov.au/copyright). Hotspots are not for safety-of-life decisions. | Digital Earth Australia Hotspots, Geoscience Australia, CC BY 4.0 | Allowed | None published; refreshed every 30 min | `open` |
| `arpansa_uv` | `https://uvdata.arpansa.gov.au/xml/uvvalues.xml` | ARPANSA | Developer conditions (https://www.arpansa.gov.au/our-services/monitoring/ultraviolet-radiation-monitoring/ultraviolet-radation-data-information): acknowledge ARPANSA ("UV observations courtesy of ARPANSA") **and notify ARPANSA that the data is used in the application**. Site copyright: no retransmission, distribution or commercial use without written approval. | UV observations courtesy of ARPANSA | Not allowed | Updated about every minute; read every poll | `restricted` (notification required, see [Permission requests](#permission-requests)) |
| `gdacs` | GDACS RSS `https://www.gdacs.org/xml/rss.xml` (through `aio-georss-gdacs`); report links `https://www.gdacs.org/report.aspx?eventtype=…&eventid=…` | European Commission Joint Research Centre | No GDACS licence found: https://www.gdacs.org/About/termofuse.aspx has a disclaimer only ("purely indicative") and links the EC legal notice (https://commission.europa.eu/legal-notice_en). The RSS `<copyright>` element says "public domain". | Global Disaster Alert and Coordination System (GDACS), European Union / JRC; indicative only | Unknown | None published; refreshed every 15 min | `unverified` |
| `nsw_air_quality` | `https://data.airquality.nsw.gov.au/api/Data/get_SiteDetails` (GET, daily), `https://data.airquality.nsw.gov.au/api/Data/get_Observations` (POST, 3 nearest sites, every 30 min) | NSW Department of Climate Change, Energy, the Environment and Water | CC BY 4.0 (data licence statement; https://data.nsw.gov.au/data/dataset/nsw-air-quality-data-services). Catalogue mirrors list CC BY 3.0 AU. | NSW Department of Climate Change, Energy, the Environment and Water, CC BY 4.0 | Allowed | None published; no key | `open` |
| `qld_air_quality` | `https://apps.des.qld.gov.au/air-quality/xml/feed.php?category=1&region=ALL` | Queensland Government | CC BY 4.0 (https://www.data.qld.gov.au/dataset/air-quality-monitoring-live-data-feed) | © State of Queensland, CC BY 4.0 | Allowed | Hourly feed; read every 30 min | `open` |
| `act_air_quality` | `https://www.data.act.gov.au/resource/94a5-zqnn.json?$order=datetime%20DESC&$limit=50` | ACT Government | CC BY 4.0 (dataset metadata, https://www.data.act.gov.au/d/94a5-zqnn) | ACT Government, CC BY 4.0 | Allowed | Socrata; read every 30 min | `open` |

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
- Emergency WA: https://www.emergency.wa.gov.au; RSS items link to their own `https://emergency.wa.gov.au/warnings/{id}` or `/incidents/{id}` page
- SA CFS: https://www.cfs.sa.gov.au
- SA SES: https://www.ses.sa.gov.au/warnings; warning documents under https://data.eso.sa.gov.au/prod/ses/sam (relative `link` values are resolved against it)
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
  `data.geojson` (#14) and, for road closures, `proxy/road-closures` (#29). Follow-up: the
  maintainer requests access (info@alert.tas.gov.au) for both.
- **NT Road Report: kept, flagged.** No terms are published for the obstruction feed (#29).
  Follow-up: ask the NT Department of Logistics and Infrastructure to confirm reuse.
- **QLDTraffic `events_v2.geojson`: kept.** The dataset is CC BY 4.0, but the keyless path is
  not in the API documentation and may change without notice (#29, supersedes #23).
- **SA: kept, flagged.** The catalogued CFS feeds are CC BY-NC-ND; nothing covers
  `cap-au.xml`. Follow-up: ask SA ESO which terms apply to the CAP-AU feed.
- **WA: switched (#61), fire danger flagged.** Warnings and incidents come from the designated RSS feeds
  (`/v1/rss/warnings`, `/v1/rss/incidents`; `/v1/cap/warnings` returned 403). Their GUIDs equal the old JSON IDs,
  so hazard IDs did not change. Fire danger ratings stay on `/v1/fire-danger-ratings` and total fire bans on
  `/v1/total-fire-bans` (#28): no designated feed publishes district ratings or per-LGA bans. Follow-up: the
  maintainer asks DFES for permission for those endpoints (or SLIP access).
  Emergency WA publishes no request-rate limit; the shared client retries 429/5xx up to 3 times.
- **Warning areas (#30): added where the terms allow.** QFD and QPS warning polygons and SA SES warnings are public
  ArcGIS layers with no licence (`unverified`, like ACT and NT); only listed fields are requested. NSW SES is not added:
  its only feed is HazardWatch (see below), and the S3 copy (`fmeims...NSW_SES_Warnings.geojson`) is a vendor copy with
  no licence. VicEmergency polygons are not used: EMV terms need written permission. ACT ESA's polygon endpoint has burnt
  areas only, with no key to join them to incidents. Follow-up: ask NSW SES for a reusable warnings feed.
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
| TasALERT | Feed access (`data.geojson` and `proxy/road-closures`) | info@alert.tas.gov.au | not yet | — |
| NT PFES / NT Government | Confirm reuse of `Fire_Incidents` | — | not yet | — |
| NT Department of Logistics and Infrastructure | Confirm reuse of the NT Road Report obstruction feed | — | not yet | — |
| SA ESO | Terms for `cap-au.xml` | — | not yet | — |
| DFES (WA) | Use of `/v1/fire-danger-ratings` and `/v1/total-fire-bans` (warnings and incidents moved to RSS, #61) or SLIP | statepublicinfo@dfes.wa.gov.au | not yet | — |
| Bureau of Meteorology | Terms for CAP warnings via WMO | — | not yet | — |
| NSW SES / HazardWatch | Feed reuse | — | not yet | — |
| ARPANSA | Notify that real-time UV data is used (a condition of use, #37) | info@arpansa.gov.au | not yet | — |

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

- Brisbane open data (CC BY 4.0), CFA feeds (CC BY 4.0, CFA only), TFS feeds (CC BY 4.0 with display conditions).
- MET Norway (https://api.met.no/doc/TermsOfService): NLOD 2.0 and CC BY 4.0, credit "Data from MET Norway"; requires an identifying User-Agent that does not start with "HomeAssistant".

## Out of scope

- XML namespace URIs (`http://www.w3.org/2005/Atom`, `http://www.georss.org/georss`, `http://purl.org/dc/elements/1.1/`, and the non-standard `https://www.ogc.org/standard/georss/` and `https://www.w3.org/2003/01/geo/wgs84_pos#` that Emergency WA's RSS declares): identifiers, never fetched.
- URLs in `script/`, `.github/workflows/`, `config/`, `tests/` and the frontend build: development tooling, test fixtures and project links, not data sources.
