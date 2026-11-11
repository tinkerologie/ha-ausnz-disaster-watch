#!/usr/bin/env python3
"""Resolve the official test plugin for a Home Assistant release or Core commit.

Print the version, plugin requirement and its source. Also write those values to
``GITHUB_OUTPUT`` when set. An empty plugin requirement indicates that no matching
plugin supports this interpreter.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import platform
import re
import ssl
import tomllib
from typing import Any
from urllib.error import HTTPError
import urllib.request

from packaging.specifiers import SpecifierSet
from packaging.version import InvalidVersion, Version

PYPI = "https://pypi.org/pypi"
PLUGIN = "pytest-homeassistant"
CORE = "https://github.com/home-assistant/core"
CORE_RAW = "https://raw.githubusercontent.com/home-assistant/core"
PLUGIN_PATH = f"packages/{PLUGIN}"
# The interpreter running this script; the workflow runs it with the venv's Python (actions/setup-python 3.14).
PYTHON = platform.python_version()


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


def newest_homeassistant() -> str:
    """Return the newest installable Home Assistant release, pre-releases included."""
    data = fetch_json(f"{PYPI}/homeassistant/json")
    releases = {
        version: [file for file in files if allows_python(file.get("requires_python"))]
        for version, files in data["releases"].items()
    }
    versions = available_versions(releases)
    if not versions:
        raise SystemExit("No Home Assistant release found on PyPI")
    return str(versions[0])


def published_plugin(ha_version: str) -> bool:
    """Check that an installable official release pins the selected Core version."""
    try:
        release = fetch_json(f"{PYPI}/{PLUGIN}/{ha_version}/json")
    except HTTPError as err:
        if err.code == 404:
            return False
        raise
    info = release["info"]
    return (
        (info.get("project_urls") or {}).get("Repository") == CORE
        and f"homeassistant=={ha_version}" in (info.get("requires_dist") or ())
        and allows_python(info.get("requires_python"))
        and any(not file.get("yanked") and allows_python(file.get("requires_python")) for file in release["urls"])
    )


def plugin_requirement(ha_version: str, core_ref: str | None = None) -> tuple[str, str]:
    """Prefer a published plugin, then try the same Core tag or commit."""
    if core_ref is None and published_plugin(ha_version):
        return f"{PLUGIN}=={ha_version}", "pypi"
    ref = core_ref or ha_version
    try:
        with urllib.request.urlopen(
            f"{CORE_RAW}/{ref}/{PLUGIN_PATH}/pyproject.toml", timeout=30, context=_ssl_context()
        ) as response:
            project = tomllib.loads(response.read().decode())["project"]
    except HTTPError as err:
        if err.code == 404:
            return "", ""
        raise
    if project["name"] != PLUGIN or not allows_python(project["requires-python"]):
        return "", ""
    return f"{PLUGIN} @ git+{CORE}.git@{ref}#subdirectory={PLUGIN_PATH}", "core-ref"


def main() -> None:
    """Print the versions and write them to ``GITHUB_OUTPUT`` when it is set."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    selector = parser.add_mutually_exclusive_group()
    selector.add_argument("--ha-version", help="Home Assistant version to use instead of the newest")
    selector.add_argument("--core-ref", help="Full commit SHA for a source build")
    args = parser.parse_args()

    if args.core_ref is not None:
        if not re.fullmatch(r"[a-f0-9]{40}", args.core_ref):
            parser.error("--core-ref requires a full lowercase commit SHA")
        ha_version = f"dev@{args.core_ref[:12]}"
    else:
        ha_version = args.ha_version or newest_homeassistant()
        if not re.fullmatch(r"[0-9]{4}\.[0-9]+\.[0-9]+(?:(?:a|b|rc)[0-9]+)?", ha_version):
            parser.error(f"invalid Home Assistant version: {ha_version}")
        info = fetch_json(f"{PYPI}/homeassistant/{ha_version}/json")["info"]
        if not allows_python(info.get("requires_python")):
            raise SystemExit(f"Home Assistant {ha_version} requires Python {info['requires_python']}, not {PYTHON}")

    requirement, source = plugin_requirement(ha_version, args.core_ref)
    result = f"ha_version={ha_version}\nplugin_requirement={requirement}\nplugin_source={source}\n"
    print(result, end="")
    if output := os.environ.get("GITHUB_OUTPUT"):
        with Path(output).open("a", encoding="utf-8") as file:
            file.write(result)


if __name__ == "__main__":
    main()
