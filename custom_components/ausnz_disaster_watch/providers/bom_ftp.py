"""Bureau of Meteorology products from the anonymous FTP server (``ftp.bom.gov.au/anon/gen/fwo/``).

BoM publishes tsunami (JATWC), heatwave and UV forecast products there; ``aiohttp`` cannot
speak FTP, so the standard library client runs in Home Assistant's executor. One call opens
one connection, lists only the requested name patterns (``NLST``), and downloads only the
matching files. An empty listing means "product not issued", which callers treat as a
confirmed all-clear; a connection or listing failure raises ProviderUnavailableError.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
import ftplib
import io
from typing import TYPE_CHECKING

from .base import ProviderUnavailableError

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

BOM_FTP_HOST = "ftp.bom.gov.au"
BOM_FTP_DIR = "/anon/gen/fwo"
BOM_FTP_TIMEOUT = 30
# A product file is at most a few hundred kilobytes; refuse anything absurd
MAX_PRODUCT_BYTES = 2_000_000


def _nlst(ftp: ftplib.FTP, pattern: str) -> list[str]:
    """List names matching ``pattern``; some servers answer "550 no files" instead of an empty list."""
    try:
        return ftp.nlst(pattern)
    except ftplib.error_perm as err:
        if str(err).startswith("550"):
            return []
        raise


def _retrieve(ftp: ftplib.FTP, name: str) -> bytes:
    buffer = io.BytesIO()

    def write(chunk: bytes) -> None:
        if buffer.tell() + len(chunk) > MAX_PRODUCT_BYTES:
            raise ftplib.Error(f"{name} is larger than {MAX_PRODUCT_BYTES} bytes")
        buffer.write(chunk)

    ftp.retrbinary(f"RETR {name}", write)
    return buffer.getvalue()


def fetch_products(patterns: tuple[str, ...], wanted: Callable[[str], bool]) -> dict[str, bytes]:
    """Blocking: return ``{name: content}`` for listed files that ``wanted`` accepts."""
    with ftplib.FTP(BOM_FTP_HOST, timeout=BOM_FTP_TIMEOUT) as ftp:
        ftp.login()
        ftp.cwd(BOM_FTP_DIR)
        names = sorted({name.rsplit("/", 1)[-1] for pattern in patterns for name in _nlst(ftp, pattern)})
        return {name: _retrieve(ftp, name) for name in names if wanted(name)}


async def async_fetch_bom_products(
    hass: HomeAssistant, patterns: Iterable[str], wanted: Callable[[str], bool]
) -> dict[str, bytes]:
    """Fetch BoM products by name pattern; raise ProviderUnavailableError if the server fails."""
    try:
        return await hass.async_add_executor_job(fetch_products, tuple(patterns), wanted)
    except ftplib.all_errors as err:
        raise ProviderUnavailableError(f"BoM FTP unavailable: {err}") from err
