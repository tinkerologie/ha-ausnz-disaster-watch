"""BoM heatwave warnings (``IDx21013.cap.xml``) as one severity per state.

A heatwave CAP document has one ``<info>`` block per district, and blocks that cancel a
district are marked ``responseType=AllClear`` / ``urgency=Past``. The state severity is the
highest of the current blocks. BoM areas carry AMOC area codes only (no shapes), so the
user's own district cannot be matched; each district's severity is kept as an attribute.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

import defusedxml.ElementTree as ET

from custom_components.ausnz_disaster_watch.models import HeatwaveArea, HeatwaveStatus

from .base import BaseHazardProvider, ProviderUnavailableError
from .cap import CAP_NS

if TYPE_CHECKING:
    from xml.etree.ElementTree import Element

HEATWAVE_PRODUCTS: dict[str, str] = {
    "NSW": "IDN21013",
    "ACT": "IDN21014",
    "NT": "IDD21013",
    "QLD": "IDQ21013",
    "SA": "IDS21013",
    "TAS": "IDT21013",
    "VIC": "IDV21013",
    "WA": "IDW21013",
}
HEATWAVE_SEVERITIES = ("none", "low_intensity", "severe", "extreme")
_CAP_SEVERITY = {"extreme": "extreme", "severe": "severe"}


def heatwave_cap_file(product_id: str) -> str:
    """Return the CAP file name of a heatwave product."""
    return f"{product_id}.cap.xml"


def _text(element: Element, path: str) -> str:
    return (element.findtext(path, "", CAP_NS) or "").strip()


def _severity(headline: str, cap_severity: str) -> str:
    text = headline.lower()
    if "extreme heatwave" in text:
        return "extreme"
    if "severe heatwave" in text:
        return "severe"
    if "low intensity" in text or "low-intensity" in text:
        return "low_intensity"
    return _CAP_SEVERITY.get(cap_severity.lower(), "low_intensity")


def heatwave_status(product_id: str, content: bytes | None, now: datetime) -> HeatwaveStatus:
    """Return the state heatwave severity; ``content`` None means the product is not issued."""
    if content is None:
        return HeatwaveStatus(severity="none", product_id=product_id)
    try:
        root = ET.fromstring(content)
    except (ET.ParseError, ValueError) as err:
        raise ProviderUnavailableError(f"Heatwave product {product_id} is invalid XML: {err}") from err
    if root.tag != f"{{{CAP_NS['cap']}}}alert":
        raise ProviderUnavailableError(f"Heatwave product {product_id} is not a CAP alert")

    parse = BaseHazardProvider.parse_datetime
    issued = parse(_text(root, "cap:sent"))
    if _text(root, "cap:status").lower() != "actual" or _text(root, "cap:msgType").lower() == "cancel":
        return HeatwaveStatus(severity="none", product_id=product_id, issued=issued)

    areas: list[HeatwaveArea] = []
    best: tuple[int, str, datetime | None] | None = None
    for info in root.findall("cap:info", CAP_NS):
        headline = _text(info, "cap:headline")
        expires = parse(_text(info, "cap:expires"))
        if (
            _text(info, "cap:responseType").lower() == "allclear"
            or _text(info, "cap:urgency").lower() == "past"
            or headline.lower().startswith("cancel")
            or (expires is not None and expires <= now)
        ):
            continue
        severity = _severity(headline, _text(info, "cap:severity"))
        rank = HEATWAVE_SEVERITIES.index(severity)
        areas.extend(
            HeatwaveArea(name=desc.rstrip(". "), severity=severity)
            for area in info.findall("cap:area", CAP_NS)
            if (desc := " ".join(_text(area, "cap:areaDesc").split()))
        )
        if best is None or rank > best[0]:
            best = (rank, headline, expires)

    if best is None:
        return HeatwaveStatus(severity="none", product_id=product_id, issued=issued)
    rank, headline, expires = best
    return HeatwaveStatus(
        severity=HEATWAVE_SEVERITIES[rank],
        areas=areas,
        headline=headline or None,
        issued=issued,
        expires=expires,
        product_id=product_id,
    )
