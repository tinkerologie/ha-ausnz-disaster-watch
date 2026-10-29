#!/usr/bin/env python3
"""Pick the Home Assistant release and test harness for the HA Next release channel.

Prints the newest non-yanked ``homeassistant`` on PyPI, pre-releases included (or
the version given with ``--ha-version``), and the newest
``pytest-homeassistant-custom-component`` release that pins exactly that version
(empty when none does yet; the harness often lags a beta by days). Resolving the
version explicitly avoids ``--prerelease allow``, which would pull pre-releases of
every dependency. With ``GITHUB_OUTPUT`` set, also writes ``ha_version`` and
``harness_version`` there.

Usage: uv run --no-project --with packaging python script/ha_next_versions.py [--ha-version X]
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import ssl
from typing import Any
import urllib.request

from packaging.requirements import InvalidRequirement, Requirement
from packaging.specifiers import SpecifierSet
from packaging.version import InvalidVersion, Version

PYPI = "https://pypi.org/pypi"
HARNESS = "pytest-homeassistant-custom-component"
PYTHON = "3.14.2"  # Keep in sync with .github/workflows/ha-next.yml
# Harness releases to inspect, newest first; one is published per Home Assistant release.
HARNESS_CANDIDATES = 15


def _ssl_context() -> ssl.SSLContext:
    """Return a TLS context with the certifi CA bundle when it is installed."""
    try:
        import certifi  # noqa: PLC0415 - optional, for Python builds without system CAs
    except ImportError:
        return ssl.create_default_context()
    return ssl.create_default_context(cafile=certifi.where())


def fetch_json(url: str) -> Any:
    """Return the JSON document at ``url``."""
    with urllib.request.urlopen(url, timeout=30, context=_ssl_context()) as response:
        return json.load(response)


def available_versions(releases: dict[str, list[dict[str, Any]]]) -> list[Version]:
    """Return the valid versions that have at least one non-yanked file, newest first."""
    versions = []
    for name, files in releases.items():
        if not files or all(file.get("yanked") for file in files):
            continue
        try:
            versions.append(Version(name))
        except InvalidVersion:
            continue
    return sorted(versions, reverse=True)


def allows_python(requires_python: str | None) -> bool:
    """Return whether a ``requires_python`` specifier allows the CI Python."""
    return not requires_python or SpecifierSet(requires_python).contains(PYTHON, prereleases=True)


def pins_homeassistant(requires_dist: list[str] | None, ha_version: str) -> bool:
    """Return whether a harness release requires exactly ``homeassistant==<ha_version>``."""
    for line in requires_dist or []:
        try:
            requirement = Requirement(line)
        except InvalidRequirement:
            continue
        if requirement.name.lower() == "homeassistant" and str(requirement.specifier) == f"=={ha_version}":
            return True
    return False


def newest_homeassistant() -> str:
    """Return the newest installable Home Assistant release, pre-releases included."""
    data = fetch_json(f"{PYPI}/homeassistant/json")
    versions = available_versions(data["releases"])
    if not versions:
        raise SystemExit("No Home Assistant release found on PyPI")
    return str(versions[0])


def matching_harness(ha_version: str) -> str:
    """Return the newest harness release that pins ``ha_version``, or an empty string."""
    data = fetch_json(f"{PYPI}/{HARNESS}/json")
    for version in available_versions(data["releases"])[:HARNESS_CANDIDATES]:
        info = fetch_json(f"{PYPI}/{HARNESS}/{version}/json")["info"]
        if pins_homeassistant(info.get("requires_dist"), ha_version) and allows_python(info.get("requires_python")):
            return str(version)
    return ""


def main() -> None:
    """Print the versions and write them to ``GITHUB_OUTPUT`` when it is set."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--ha-version", default="", help="Home Assistant version to use instead of the newest")
    args = parser.parse_args()

    ha_version = args.ha_version or newest_homeassistant()
    info = fetch_json(f"{PYPI}/homeassistant/{ha_version}/json")["info"]
    if not allows_python(info.get("requires_python")):
        raise SystemExit(f"Home Assistant {ha_version} requires Python {info['requires_python']}, not {PYTHON}")
    harness_version = matching_harness(ha_version)

    print(f"ha_version={ha_version}")
    print(f"harness_version={harness_version}")
    if output := os.environ.get("GITHUB_OUTPUT"):
        with Path(output).open("a", encoding="utf-8") as file:
            file.write(f"ha_version={ha_version}\nharness_version={harness_version}\n")


if __name__ == "__main__":
    main()
