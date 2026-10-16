#!/usr/bin/env python3
"""Generate the council disaster dashboard registry (#32).

Writes ``custom_components/ausnz_disaster_watch/data/council_dashboards.json``: every QLD and
NSW council dashboard that is a live Guardian IMS (QIT Plus) dashboard, with the council's
name, state, dashboard URL and a representative point.

Inputs:

- Queensland: the official CSV of all 77 council disaster dashboards on qld.gov.au
  ("Local Government", "Website", "Disaster Dashboard or disaster web page").
- NSW: ``NSW_DASHBOARDS`` below. No NSW list exists; these are the NSW councils known to run
  Guardian IMS. Demonz dashboards (``*.disasterdashboards.com``) are never added: their API
  says "Unauthorised use is not permitted".
- Location: ABS ASGS 2024 Local Government Areas (CC BY 4.0): the LGA centroid, and an
  equal-area radius (``sqrt(area / pi)``) so large rural councils match beyond 40 km. The
  original eleven presets keep their name and point (``LEGACY_PRESETS``).

A dashboard counts as live Guardian IMS when ``<url>/dashboard/bom`` or
``<url>/dashboard/getTemplateWidgets`` answers HTTP 200 with JSON. Redirects are followed
and the final host is recorded. A council that was listed before but does not answer now is
kept (with a warning) unless ``--prune`` is given, so one bad night does not drop it.

Councils on other platforms are listed with ``url: null`` and their ``platform``, so their
location stays selectable (Sunshine Coast Disaster Hub, Brisbane's ArcGIS dashboard).

The output is sorted and has no timestamp, so a run without changes leaves the file
unchanged. Uses the standard library only.

Usage: script/update-councils [--prune] [--dry-run]
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import csv
import io
import json
import math
from pathlib import Path
import re
import ssl
import sys
import time
from typing import Any
import urllib.error
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "custom_components" / "ausnz_disaster_watch" / "data" / "council_dashboards.json"

QLD_CSV_URL = "https://www.qld.gov.au/community/disasters-emergencies/disasters/resources-translations?a=228165"
ABS_LGA_URL = "https://geo.abs.gov.au/arcgis/rest/services/ASGS2024/LGA/FeatureServer/0/query"
ABS_STATE_CODES = {"NSW": "1", "QLD": "3"}
USER_AGENT = "AusNZDisasterWatch-registry/1.0 (+https://github.com/tinkerologie/ha-ausnz-disaster-watch)"
DENYLIST_SUFFIXES = ("disasterdashboards.com",)

# NSW councils known to run Guardian IMS (from the integration's council links, #12/#25)
NSW_DASHBOARDS = {
    "Ballina Shire Council": "https://emergency.ballina.nsw.gov.au",
    "Blue Mountains City Council": "https://emergency.bmcc.nsw.gov.au",
    "Byron Shire Council": "https://emergency.byron.nsw.gov.au",
    "Hawkesbury City Council": "https://disaster.hawkesbury.nsw.gov.au",
    "Northern Beaches Council": "https://emergency.northernbeaches.nsw.gov.au",
}

# Councils whose dashboard is not Guardian IMS (verified 2026-10-16); kept selectable without a URL
OTHER_PLATFORMS = {
    ("QLD", "Brisbane"): "brisbane_arcgis",  # ArcGIS Experience app, no Guardian endpoints
    ("QLD", "Sunshine Coast"): "sunshine_hub",  # Disaster Hub web app
}

# The integration's original presets keep their display name and point, so new entries
# made from them get the same title and unique ID as before (#32)
LEGACY_PRESETS = {
    "moreton_bay": ("City of Moreton Bay", -27.2657, 152.9818),
    "sunshine_coast": ("Sunshine Coast", -26.6500, 153.0667),
    "noosa": ("Noosa Shire", -26.3986, 153.0442),
    "gold_coast": ("City of Gold Coast", -28.0167, 153.4000),
    "cairns": ("Cairns Regional", -16.9186, 145.7781),
    "townsville": ("Townsville City", -19.2590, 146.8169),
    "fraser_coast": ("Fraser Coast", -25.5398, 152.7032),
    "bundaberg": ("Bundaberg Regional", -24.8661, 152.3489),
    "redland": ("Redland City", -27.5306, 153.2500),
    "ipswich": ("Ipswich City", -27.6167, 152.7667),
    "logan": ("Logan City", -27.6972, 153.1111),
}

# CSV and ABS names that differ after normalisation
NAME_FIXES = {"weipa town": "weipa"}

_SUFFIXES = re.compile(
    r"\b(aboriginal shire council|aboriginal shire|regional council|shire council|city council|"
    r"town council|council|regional|shire|city)\b"
)


def norm(name: str) -> str:
    """Normalise a council or LGA name for matching ("Mount Isa City Council" -> "mount isa")."""
    text = re.sub(r"\([^)]*\)", "", name.lower()).replace("-", " ")
    text = NAME_FIXES.get(text.strip(), text)
    text = _SUFFIXES.sub("", text)
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def slug(name: str) -> str:
    """Return a registry key ("Moreton Bay" -> "moreton_bay")."""
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


def _ssl_context(verify: bool) -> ssl.SSLContext:
    """Return Home Assistant's kind of TLS context (certifi CA bundle), or an unverified one."""
    if not verify:
        # Only used to tell a dashboard with a broken certificate chain from a dead host
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        return context
    try:
        import certifi  # noqa: PLC0415 - optional; Home Assistant verifies against certifi

        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()


CERT_ERROR = -1  # fetch status: the certificate could not be verified


def fetch(url: str, timeout: float = 30, verify: bool = True) -> tuple[int, str, bytes]:
    """GET a URL; return (status, final URL, body). Network errors give 0, certificate errors CERT_ERROR."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json, */*"})
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=_ssl_context(verify)) as resp:
            return resp.status, resp.geturl(), resp.read()
    except urllib.error.HTTPError as err:
        return err.code, url, b""
    except urllib.error.URLError as err:
        return (CERT_ERROR if isinstance(err.reason, ssl.SSLCertVerificationError) else 0), url, b""
    except (TimeoutError, OSError):
        return 0, url, b""


def dashboard_base(url: str) -> str | None:
    """Return ``https://host[/prefix]`` for a dashboard URL from the CSV, or None."""
    raw = url.strip()
    if not raw:
        return None
    if "://" not in raw:
        raw = f"https://{raw}"
    parts = urllib.parse.urlsplit(raw)
    host = (parts.hostname or "").lower()
    if not host or host.endswith(DENYLIST_SUFFIXES):
        return None
    return f"https://{host}{parts.path.rstrip('/')}"


def probe_guardian(base: str) -> tuple[str | None, bool]:
    """Return (live base URL or None, certificate verifies) for a candidate dashboard.

    Network errors and 5xx are retried (dashboards share hosting and time out under load).
    A dashboard whose certificate chain is incomplete (browsers fetch the missing
    intermediate, Home Assistant does not) is still reported, with ``False``.
    """
    status = 0
    for verify in (True, False):
        for endpoint in ("bom", "getTemplateWidgets"):
            for attempt in range(3):
                status, final, body = fetch(f"{base}/dashboard/{endpoint}", verify=verify)
                if status == 0 or status >= 500:
                    time.sleep(2 * (attempt + 1))
                    continue
                break
            if status == CERT_ERROR:
                break  # retry the whole probe without verification
            if status != 200:
                continue
            try:
                json.loads(body)
            except ValueError:
                continue
            final_base = final.split("/dashboard/", 1)[0]
            parts = urllib.parse.urlsplit(final_base)
            return f"https://{(parts.hostname or '').lower()}{parts.path.rstrip('/')}", verify
        if status != CERT_ERROR:
            break
    print(f"not a live Guardian IMS dashboard: {base} (HTTP {status or 'error'})", file=sys.stderr)
    return None, True


def load_lgas(state: str) -> dict[str, dict[str, Any]]:
    """Return ABS LGAs of a state, with centroid and equal-area radius, keyed by normalised name."""
    query = urllib.parse.urlencode(
        {
            "where": f"state_code_2021='{ABS_STATE_CODES[state]}'",
            "outFields": "lga_name_2024,lga_code_2024,area_albers_sqkm",
            "returnGeometry": "false",
            "returnCentroid": "true",
            "outSR": "4326",
            "f": "json",
        }
    )
    status, _, body = fetch(f"{ABS_LGA_URL}?{query}", timeout=60)
    payload = json.loads(body) if status == 200 else {}
    if "features" not in payload:
        sys.exit(f"ABS LGA query failed for {state}: HTTP {status} {payload.get('error')}")
    lgas: dict[str, dict[str, Any]] = {}
    for feat in payload["features"]:
        attrs, centroid = feat["attributes"], feat.get("centroid")
        if not centroid or not attrs.get("area_albers_sqkm"):
            continue  # "No usual address" and "Migratory" pseudo-areas have no shape
        name = attrs["lga_name_2024"]
        lgas[norm(name)] = {
            "lga_name": re.sub(r"\s*\([^)]*\)", "", name).strip(),
            "lga_code": attrs["lga_code_2024"],
            "latitude": round(centroid["y"], 4),
            "longitude": round(centroid["x"], 4),
            "radius_km": round(math.sqrt(attrs["area_albers_sqkm"] / math.pi), 1),
        }
    return lgas


def load_qld_csv() -> dict[str, str]:
    """Return {council name: dashboard URL} from the official QLD CSV."""
    status, _, body = fetch(QLD_CSV_URL)
    if status != 200:
        sys.exit(f"QLD council CSV download failed (HTTP {status})")
    rows = csv.DictReader(io.StringIO(body.decode("utf-8-sig")))
    expected = {"Local Government", "Disaster Dashboard or disaster web page"}
    if not expected <= set(rows.fieldnames or ()):
        sys.exit(f"QLD council CSV headers changed: {rows.fieldnames}")
    return {
        row["Local Government"].strip(): row["Disaster Dashboard or disaster web page"].strip()
        for row in rows
        if row["Local Government"].strip()
    }


def build(prune: bool) -> list[dict[str, Any]]:
    """Probe every candidate dashboard and return the sorted registry entries."""
    previous: dict[str, dict[str, Any]] = {}
    if OUTPUT.exists():
        previous = {c["key"]: c for c in json.loads(OUTPUT.read_text(encoding="utf-8"))["councils"]}

    candidates = [("QLD", name, url) for name, url in load_qld_csv().items()]
    candidates += [("NSW", name, url) for name, url in NSW_DASHBOARDS.items()]
    lgas = {state: load_lgas(state) for state in ABS_STATE_CODES}

    def check(candidate: tuple[str, str, str]) -> tuple[tuple[str, str, str], str | None, bool]:
        _, _, url = candidate
        base = dashboard_base(url)
        live, certificate_ok = probe_guardian(base) if base else (None, True)
        return candidate, live, certificate_ok

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(check, candidates))

    councils: dict[str, dict[str, Any]] = {}
    for (state, name, url), live, certificate_ok in results:
        lga = lgas[state].get(norm(name))
        if lga is None:
            sys.exit(f"No ABS LGA matches {name!r} ({state}); add a NAME_FIXES entry")
        platform = OTHER_PLATFORMS.get((state, lga["lga_name"]))
        key = slug(lga["lga_name"])
        if key in councils:
            key = f"{key}_{state.lower()}"
        entry = {
            "key": key,
            # "Toowoomba Regional Council" -> "Toowoomba Regional", like the original presets
            "name": re.sub(r"\s+Council$", "", name),
            "lga": lga["lga_name"],
            "state": state,
            "url": live,
            "platform": platform or "guardian",
            "latitude": lga["latitude"],
            "longitude": lga["longitude"],
            "radius_km": lga["radius_km"],
            "lga_code": lga["lga_code"],
            # False: the server sends an incomplete certificate chain, which Home Assistant
            # (certifi, no AIA fetching) rejects, so the dashboard cannot be read until fixed
            "certificate_ok": certificate_ok,
        }
        if key in LEGACY_PRESETS:
            entry["name"], entry["latitude"], entry["longitude"] = LEGACY_PRESETS[key]
        if platform:
            entry["url"] = None
            entry["certificate_ok"] = True
        elif live is None:
            if key in previous and previous[key].get("url") and not prune:
                print(f"warning: {name} ({url}) did not answer; keeping {previous[key]['url']}", file=sys.stderr)
                entry["url"] = previous[key]["url"]
                entry["certificate_ok"] = previous[key].get("certificate_ok", True)
            else:
                continue  # not a Guardian IMS dashboard (a web page, another platform, or offline)
        councils[key] = entry

    for key in sorted(set(previous) - set(councils)):
        print(f"removed: {key} ({previous[key].get('url')})")
    for key in sorted(set(councils) - set(previous)):
        print(f"added: {key} ({councils[key]['url'] or councils[key]['platform']})")
    for key in sorted(set(councils) & set(previous)):
        if councils[key] != previous[key]:
            print(f"changed: {key}")
    return [councils[key] for key in sorted(councils)]


def main() -> None:
    """Generate the registry file."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--prune", action="store_true", help="drop councils whose dashboard does not answer")
    parser.add_argument("--dry-run", action="store_true", help="print the summary without writing the file")
    args = parser.parse_args()

    councils = build(args.prune)
    document = {
        "schema_version": 1,
        "sources": {
            "qld_councils": QLD_CSV_URL,
            "nsw_councils": "script/update_councils.py NSW_DASHBOARDS",
            "locations": "ABS ASGS 2024 Local Government Areas (CC BY 4.0): centroid and equal-area radius",
            "guardian_check": "<url>/dashboard/bom or /dashboard/getTemplateWidgets answers HTTP 200 with JSON",
        },
        "councils": councils,
    }
    text = json.dumps(document, indent=2, ensure_ascii=False) + "\n"
    guardian = sum(1 for c in councils if c["url"])
    print(f"{len(councils)} councils ({guardian} live Guardian IMS dashboards)")
    if not args.dry_run:
        OUTPUT.write_text(text, encoding="utf-8")
        print(f"wrote {OUTPUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
