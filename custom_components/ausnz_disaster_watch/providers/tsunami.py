"""Tsunami threat status: JATWC CAP products for Australia, PTWC guidance for New Zealand.

JATWC (the Joint Australian Tsunami Warning Centre, run by BoM and Geoscience Australia)
issues CAP-AU products ``IDY680nn`` only while an event is in progress, so an absent product
after a successful listing is a confirmed "no tsunami threat". Product IDs follow the BoM
warnings guide; no live product existed when this was written, so the parsing is tested
against a synthetic CAP-AU fixture.

PTWC (NOAA Pacific Tsunami Warning Center) is international guidance, not an official New
Zealand warning; official NZ tsunami warnings come from NEMA through the NZ provider. A PTWC
message only counts as a threat to New Zealand when its text names New Zealand outside the
earthquake location fields: the epicentre is never treated as the threatened area.
"""

from __future__ import annotations

from datetime import datetime
import re

import defusedxml.ElementTree as ET

from custom_components.ausnz_disaster_watch.models import TsunamiStatus

from .base import ProviderUnavailableError
from .cap import CapAlert, parse_cap

JATWC_SOURCE = "Joint Australian Tsunami Warning Centre (JATWC)"
PTWC_SOURCE = "Pacific Tsunami Warning Center (international guidance, not an official NZ warning)"
PTWC_ATOM_URL = "https://www.tsunami.gov/events/xml/PHEBAtom.xml"

# National products: watch, no threat, and the national summary
JATWC_NATIONAL_PRODUCTS = ("IDY68005", "IDY68009", "IDY68020")
JATWC_NO_THREAT_PRODUCT = "IDY68009"
# State bulletins (BoM warnings guide). ACT has none and relies on the national products.
JATWC_STATE_PRODUCTS: dict[str, str] = {
    "WA": "IDY68025",
    "NT": "IDY68026",
    "QLD": "IDY68027",
    "NSW": "IDY68028",
    "VIC": "IDY68029",
    "SA": "IDY68030",
    "TAS": "IDY68031",
}
JATWC_FTP_PATTERN = "IDY68*"

THREAT_RANK = {"no_threat": 0, "watch": 1, "marine": 2, "land": 3}
_LAND_RE = re.compile(r"\bland\b")
_MARINE_RE = re.compile(r"\bmarine\b")

_ATOM = "{http://www.w3.org/2005/Atom}"
# PTWC parameters that describe the earthquake itself rather than the threatened coasts
_PTWC_EPICENTRE_PARAMETERS = {"eventlocationname", "eventlatlon"}


def jatwc_products(state: str) -> tuple[str, ...]:
    """Return the JATWC products that apply to a jurisdiction (national plus its state bulletin)."""
    bulletin = JATWC_STATE_PRODUCTS.get(state.upper())
    return (*JATWC_NATIONAL_PRODUCTS, bulletin) if bulletin else JATWC_NATIONAL_PRODUCTS


def _product_of(name: str) -> str:
    return name[:8]


def is_jatwc_cap_file(name: str) -> bool:
    """Return True for a JATWC CAP document (``IDY680nn.cap.xml`` or ``IDY680nn_cap.xml``)."""
    return name.startswith("IDY68") and name.lower().endswith("cap.xml")


def _is_current(alert: CapAlert, now: datetime) -> bool:
    if alert.status.lower() != "actual" or alert.msg_type.lower() == "cancel":
        return False
    if alert.headline.lower().startswith("cancel"):
        return False
    return alert.expires is None or alert.expires > now


def _threat_level(product: str, alert: CapAlert) -> str:
    """Derive the JATWC threat category from the product and the stated warning text."""
    text = f"{alert.event} {alert.headline}".lower()
    if product == JATWC_NO_THREAT_PRODUCT or "no threat" in text:
        return "no_threat"
    # Whole words only: place names such as "Queensland" or "Island" must not read as a land threat
    if _LAND_RE.search(text):
        return "land"
    if _MARINE_RE.search(text):
        return "marine"
    # A current tsunami product of unknown wording is treated as a watch, never as clear
    return "watch"


def _applies_to(product: str, alert: CapAlert, state: str) -> bool:
    if product in jatwc_products(state):
        return True
    region = f"AU-{state.upper()}"
    return any(value.upper() == region for area in alert.areas for _, value in area.geocodes)


def jatwc_status(files: dict[str, bytes], state: str, now: datetime) -> TsunamiStatus:
    """Return the tsunami status from the JATWC CAP files present on the BoM server.

    Raises ProviderUnavailableError if a present product cannot be parsed: it could be the
    warning, so the status is undetermined rather than clear.
    """
    best: tuple[str, CapAlert] | None = None
    present: list[str] = []
    for name, content in sorted(files.items()):
        product = _product_of(name)
        alert = parse_cap(content.decode("utf-8", errors="replace"))
        if alert is None:
            raise ProviderUnavailableError(f"JATWC product {name} is not a CAP alert")
        if not _applies_to(product, alert, state):
            continue
        present.append(product)
        if not _is_current(alert, now):
            continue
        level = _threat_level(product, alert)
        if best is None or THREAT_RANK[level] > THREAT_RANK[best[0]]:
            best = (level, alert)
    if best is None:
        return TsunamiStatus(active=False, products=present, source=JATWC_SOURCE, checked_at=now)
    level, alert = best
    return TsunamiStatus(
        active=level != "no_threat",
        threat_level=level,
        headline=alert.headline or alert.event,
        issued=alert.sent,
        expires=alert.expires,
        products=present,
        source=JATWC_SOURCE,
        checked_at=now,
    )


def ptwc_cap_links(xml_text: str) -> list[str]:
    """Return the CAP document links of the PTWC Atom feed's entries."""
    try:
        root = ET.fromstring(xml_text)
    except (ET.ParseError, ValueError) as err:
        raise ProviderUnavailableError(f"PTWC feed returned invalid XML: {err}") from err
    if root.tag != f"{_ATOM}feed":
        raise ProviderUnavailableError(f"PTWC feed returned an unexpected document <{root.tag}>")
    hrefs = (
        (link.get("href") or "").strip()
        for entry in root.findall(f"{_ATOM}entry")
        for link in entry.findall(f"{_ATOM}link")
        if link.get("type") == "application/cap+xml"
    )
    return [href for href in hrefs if href]


def _names_new_zealand(alert: CapAlert) -> bool:
    texts = [alert.headline, alert.description]
    texts += [value for name, value in alert.parameters if name.lower() not in _PTWC_EPICENTRE_PARAMETERS]
    return any("new zealand" in text.lower() for text in texts)


def ptwc_status(alerts: list[CapAlert], now: datetime) -> TsunamiStatus:
    """Return the PTWC guidance status for New Zealand from the current PTWC CAP messages."""
    for alert in sorted(alerts, key=lambda a: a.sent or now, reverse=True):
        event = alert.event.lower()
        if not _is_current(alert, now) or "information" in event:
            continue
        if _names_new_zealand(alert):
            return TsunamiStatus(
                active=True,
                threat_level="watch",
                headline=alert.headline.strip() or alert.event,
                issued=alert.sent,
                expires=alert.expires,
                products=[alert.identifier],
                source=PTWC_SOURCE,
                checked_at=now,
            )
    return TsunamiStatus(
        active=False,
        products=[alert.identifier for alert in alerts],
        source=PTWC_SOURCE,
        checked_at=now,
    )
