#!/usr/bin/env python3
"""Generate the emergency broadcaster table (#73).

Writes ``custom_components/ausnz_disaster_watch/data/emergency_broadcasters.json``: every ABC
Local Radio region (Australia's official emergency broadcaster) and RNZ National (a New
Zealand lifeline broadcaster), each with an HTTPS stream URL and an approximate location.

Inputs:

- Radio Browser (https://api.radio-browser.info/, directory data PDDL 1.0): the geolocated
  ABC stations of Australia. A mirror is picked from the DNS name ``all.api.radio-browser.info``
  as the API documentation asks, and requests carry an identifying User-Agent. The directory
  is noisy (duplicates, dated "20220701" entries, Akamai and Icecast mirrors), so only
  stations whose resolved URL is ``https://streaming.abc-cdn.net.au/audio/hls/local<region>.m3u8``
  are used, one per region. The location is the station's directory location (its studio),
  not the centre of its coverage area.
- ABC listen (``https://www.abc.net.au/listen/live/<region>``): the station's official name
  ("ABC Brisbane"). A region whose page does not answer keeps its directory name, with a
  warning to check it by hand.
- RNZ: RNZ's own player at https://www.rnz.co.nz/national streams RNZ National over HTTPS
  from ``radionz.streamguys1.com`` (the directory's ``radionz-ice.streamguys.com`` URL is HTTP
  only; its HTTPS certificate does not match the host).

Every stream is fetched once and must answer with an HLS playlist (``#EXTM3U``). A new
station whose stream does not answer is left out. A station already in the table is kept
through one failed run (its row records ``failed_checks``) and removed when the next run
fails too; a station that left the directory is kept only while its stream still answers. The output is sorted; ``refreshed`` is
the date of the run. Uses the standard library only.

Usage: script/update-broadcasters [--dry-run]
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
import json
from pathlib import Path
import re
import socket
import ssl
import sys
from typing import Any
import urllib.error
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "custom_components" / "ausnz_disaster_watch" / "data" / "emergency_broadcasters.json"

USER_AGENT = "AusNZDisasterWatch-broadcasters/1.0 (+https://github.com/tinkerologie/ha-ausnz-disaster-watch)"
RADIO_BROWSER_DNS = "all.api.radio-browser.info"
RADIO_BROWSER_FALLBACK = "de1.api.radio-browser.info"
RADIO_BROWSER_SEARCH = "https://{host}/json/stations/search"
ABC_STREAM = "https://streaming.abc-cdn.net.au/audio/hls/{slug}.m3u8"
ABC_STREAM_RE = re.compile(r"^https://streaming\.abc-cdn\.net\.au/audio/hls/(local[a-z]+)\.m3u8(?:\?.*)?$")
ABC_LISTEN_PAGE = "https://www.abc.net.au/listen/live/{region}"
ABC_TITLE_RE = re.compile(r'"title":"(ABC [^"]+?) Live Audio"')
RNZ_NATIONAL_STREAM = "https://radionz.streamguys1.com/national/national/playlist.m3u8"
RNZ_PLAYER_PAGE = "https://www.rnz.co.nz/national"
HLS_MIME_TYPE = "application/vnd.apple.mpegurl"
# Consecutive runs a stream may fail its check before its row is removed
MAX_FAILED_CHECKS = 2

STATES = {
    "new south wales": "NSW",
    "victoria": "VIC",
    "queensland": "QLD",
    "western australia": "WA",
    "south australia": "SA",
    "tasmania": "TAS",
    "australian capital territory": "ACT",
    "northern territory": "NT",
}


def _context() -> ssl.SSLContext:
    """Return Home Assistant's kind of TLS context (certifi CA bundle when installed)."""
    try:
        import certifi  # noqa: PLC0415 - optional; Home Assistant verifies against certifi

        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()


CONTEXT = _context()


def fetch(url: str, *, limit: int = 2_000_000, user_agent: str = USER_AGENT) -> tuple[int, str, str]:
    """Return (status, content type, body text) for a GET; status -1 on a connection or TLS error."""
    request = urllib.request.Request(url, headers={"User-Agent": user_agent})
    try:
        with urllib.request.urlopen(request, timeout=30, context=CONTEXT) as response:
            body = response.read(limit).decode("utf-8", "replace")
            return response.status, response.headers.get("Content-Type", ""), body
    except urllib.error.HTTPError as err:
        return err.code, "", ""
    except (urllib.error.URLError, OSError) as err:
        return -1, str(err), ""


def radio_browser_host() -> str:
    """Return a Radio Browser mirror host name, found as the API documentation describes."""
    try:
        addresses = socket.getaddrinfo(RADIO_BROWSER_DNS, 443, proto=socket.IPPROTO_TCP)
        for address in sorted({info[4][0] for info in addresses}):
            host = socket.gethostbyaddr(address)[0]
            if host.endswith(".api.radio-browser.info"):
                return host
    except OSError:
        pass
    return RADIO_BROWSER_FALLBACK


def search(host: str, **params: str) -> list[dict[str, Any]]:
    """Run a Radio Browser station search."""
    url = f"{RADIO_BROWSER_SEARCH.format(host=host)}?{urllib.parse.urlencode(params)}"
    status, _, body = fetch(url)
    if status != 200:
        sys.exit(f"Radio Browser search failed ({status}): {url}")
    return json.loads(body)


def state_code(name: str) -> str | None:
    """Return the state code for a Radio Browser state name such as "Queensland" or "Sydney NSW"."""
    lowered = name.lower()
    return next((code for state, code in STATES.items() if state in lowered), None)


def stream_is_live(url: str) -> bool:
    """Return True if a stream answers with an HLS playlist."""
    status, content_type, body = fetch(url, limit=4096)
    return status == 200 and "mpegurl" in content_type.lower() and body.startswith("#EXTM3U")


def abc_stations(host: str) -> dict[str, dict[str, Any]]:
    """Return one table row per ABC Local Radio region found in the directory."""
    found = search(host, countrycode="AU", name="ABC", hidebroken="true", has_geo_info="true", limit="500")
    by_slug: dict[str, list[dict[str, Any]]] = {}
    for station in found:
        if match := ABC_STREAM_RE.match(station.get("url_resolved") or ""):
            by_slug.setdefault(match.group(1), []).append(station)
    rows: dict[str, dict[str, Any]] = {}
    for slug, stations in sorted(by_slug.items()):
        # Prefer a station that passed its last check, then the most used, then a stable tie-break
        best = min(
            stations, key=lambda s: (-int(s.get("lastcheckok") or 0), -int(s.get("clickcount") or 0), s["stationuuid"])
        )
        state = state_code(best.get("state") or "")
        if state is None:
            print(f"warning: {slug}: unknown state {best.get('state')!r}; skipped", file=sys.stderr)
            continue
        region = slug.removeprefix("local")
        rows[f"abc_{region}"] = {
            "key": f"abc_{region}",
            "name": best["name"].strip(),
            "network": "ABC Local Radio",
            "country": "AU",
            "state": state,
            "region": region,
            "latitude": round(float(best["geo_lat"]), 4),
            "longitude": round(float(best["geo_long"]), 4),
            "stream_url": ABC_STREAM.format(slug=slug),
            "mime_type": HLS_MIME_TYPE,
            "station_page": ABC_LISTEN_PAGE.format(region=region),
            "stationuuid": best["stationuuid"],
        }
    return rows


def name_from_abc(row: dict[str, Any]) -> None:
    """Replace the directory name with the station's official name from its ABC listen page."""
    status, _, page = fetch(row["station_page"], user_agent="Mozilla/5.0")
    if status == 200 and (match := ABC_TITLE_RE.search(page)):
        row["name"] = json.loads(f'"{match.group(1)}"')  # undo JSON escapes such as &
    else:
        print(
            f"warning: {row['key']}: ABC listen page {status}; check the name {row['name']!r} by hand", file=sys.stderr
        )


def rnz_national(host: str) -> dict[str, Any]:
    """Return the RNZ National row; the location is the directory's (centre of New Zealand)."""
    found = search(host, countrycode="NZ", name="RNZ National", has_geo_info="true", limit="20")
    if not found:
        sys.exit("Radio Browser has no geolocated RNZ National station")
    station = min(found, key=lambda s: s["stationuuid"])
    return {
        "key": "rnz_national",
        "name": "RNZ National",
        "network": "RNZ",
        "country": "NZ",
        "state": "NZ",
        "region": "national",
        "latitude": round(float(station["geo_lat"]), 4),
        "longitude": round(float(station["geo_long"]), 4),
        "stream_url": RNZ_NATIONAL_STREAM,
        "mime_type": HLS_MIME_TYPE,
        "station_page": RNZ_PLAYER_PAGE,
        "stationuuid": station["stationuuid"],
    }


def load_existing() -> dict[str, dict[str, Any]]:
    """Return the current table by key (empty when there is none)."""
    if not OUTPUT.exists():
        return {}
    return {row["key"]: row for row in json.loads(OUTPUT.read_text(encoding="utf-8"))["stations"]}


def main() -> int:
    """Build the table and write it, printing what changed."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dry-run", action="store_true", help="print the summary without writing")
    args = parser.parse_args()

    host = radio_browser_host()
    print(f"Radio Browser mirror: {host}")
    rows = abc_stations(host)
    rows["rnz_national"] = rnz_national(host)

    with ThreadPoolExecutor(8) as pool:
        list(pool.map(name_from_abc, [row for row in rows.values() if row["network"] == "ABC Local Radio"]))
        live = dict(zip(rows, pool.map(stream_is_live, [row["stream_url"] for row in rows.values()]), strict=True))

    existing = load_existing()
    for key in sorted(set(existing) - set(rows)):
        # Gone from the directory: keep it only while its stream still answers
        if stream_is_live(existing[key]["stream_url"]):
            print(f"warning: {key}: no longer in the directory; keeping it (its stream still answers)", file=sys.stderr)
            rows[key] = {k: v for k, v in existing[key].items() if k != "failed_checks"}
            live[key] = True
        else:
            print(f"warning: {key}: no longer in the directory and its stream is dead; removed", file=sys.stderr)
    for key, ok in live.items():
        if ok:
            continue
        failed = int(existing.get(key, {}).get("failed_checks", 0)) + 1
        if key in existing and failed < MAX_FAILED_CHECKS:
            # Bridge one bad run; a stream that fails again on the next run is removed
            print(f"warning: {key}: stream did not answer; kept (failed check {failed})", file=sys.stderr)
            rows[key] = {**existing[key], "failed_checks": failed}
        else:
            print(f"warning: {key}: stream did not answer; removed", file=sys.stderr)
            del rows[key]

    added = sorted(set(rows) - set(existing))
    changed = sorted(key for key in set(rows) & set(existing) if rows[key] != existing[key])
    print(
        f"{len(rows)} stations ({sum(row['country'] == 'AU' for row in rows.values())} ABC); added {added}; changed {changed}"
    )
    if args.dry_run:
        return 0

    table = {
        "schema_version": 1,
        "refreshed": datetime.now(UTC).date().isoformat(),
        "sources": {
            "directory": "Radio Browser https://api.radio-browser.info/ (PDDL 1.0); location is the station's directory location",
            "abc_names": "ABC listen station pages https://www.abc.net.au/listen/live/<region>",
            "abc_streams": "https://streaming.abc-cdn.net.au/audio/hls/local<region>.m3u8 (ABC's own HLS streams)",
            "rnz_stream": "RNZ's player at https://www.rnz.co.nz/national (HTTPS HLS)",
            "generator": "script/update-broadcasters",
        },
        "stations": [rows[key] for key in sorted(rows)],
    }
    OUTPUT.write_text(json.dumps(table, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {OUTPUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
