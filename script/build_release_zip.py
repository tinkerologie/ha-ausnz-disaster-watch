#!/usr/bin/env python3
"""Build the reproducible release zip that HACS and the Marketplace install (#120).

The zip holds the contents of ``custom_components/ausnz_disaster_watch/`` at its root
(``manifest.json`` at the top level). HACS extracts it into
``config/custom_components/ausnz_disaster_watch/``. ``SHA256SUMS`` is written next to it.

Only files Git tracks are packaged, and the build fails when a tracked file under the
integration differs from ``HEAD``, so local edits and leftovers never ship. Before
anything is written the file list is checked: the files the integration loads at runtime
are present (data tables, translations, brand images, the dashboard card bundle), and every
module the frontend bundle imports, statically or lazily, resolves inside the zip.

The same commit always builds a byte-identical zip: entries are sorted, every timestamp
comes from ``SOURCE_DATE_EPOCH`` (or the ``HEAD`` commit time), and permissions and
compression settings are fixed. Uses the standard library only.

Usage: script/build-release [--output-dir dist] [--version v2026.10.1]
"""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import posixpath
import re
import subprocess
import sys
import time
import zipfile

REPO_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_DIR = REPO_ROOT / "custom_components" / "ausnz_disaster_watch"
HACS_JSON = REPO_ROOT / "hacs.json"
CHECKSUMS_NAME = "SHA256SUMS"

# 1980-01-01T00:00:00Z, the earliest timestamp a zip entry can store.
ZIP_EPOCH = 315532800
FILE_MODE = 0o100644  # regular file, rw-r--r--
COMPRESS_LEVEL = 9
BYTECODE_SUFFIXES = (".pyc", ".pyo")
FRONTEND_ENTRY = "frontend/ausnz-disaster-card.js"

# Files Home Assistant needs to load the integration and that the code reads at runtime:
# council_registry.py, broadcaster.py and fire_districts.py read data/, frontend.py serves
# frontend/, and Home Assistant reads the translations, icons and brand images.
REQUIRED_FILES = (
    "__init__.py",
    "manifest.json",
    "icons.json",
    "quality_scale.yaml",
    "translations/en.json",
    "frontend.py",
    "data/council_dashboards.json",
    "data/emergency_broadcasters.json",
    "data/fire_districts.json",
    "brand/icon.png",
    "brand/icon@2x.png",
    "brand/logo.png",
    "brand/logo@2x.png",
    "brand/dark_logo.png",
    "brand/dark_logo@2x.png",
    FRONTEND_ENTRY,
)

# Static imports, re-exports, side-effect imports (minified ``from"./x.js"`` included) and
# dynamic ``import("./x.js")`` with a single-, double- or backtick-quoted literal.
JS_IMPORT = re.compile(r"""(?:\bfrom|\bimport)\s*(?:\(\s*)?(["'`])([^"'`\n]*)\1""")
# Any dynamic import call, to catch one whose argument is not a plain literal.
JS_DYNAMIC_IMPORT = re.compile(r"""\bimport\s*\(\s*(["'`]?)""")


class ReleaseZipError(Exception):
    """Raised when the release zip cannot be built."""


def _git(*args: str) -> str:
    """Run Git in the repository and return its standard output."""
    try:
        result = subprocess.run(
            ["git", "-C", str(REPO_ROOT), *args],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError) as err:
        raise ReleaseZipError(f"git {' '.join(args)} failed; is {REPO_ROOT} a Git work tree?") from err
    return result.stdout


def zip_name(hacs_json: Path = HACS_JSON) -> str:
    """Return the asset name from ``filename`` in ``hacs.json``, the single source for it."""
    data = json.loads(hacs_json.read_text(encoding="utf-8"))
    name = data.get("filename")
    if not data.get("zip_release") or not isinstance(name, str) or not name.endswith(".zip"):
        raise ReleaseZipError("hacs.json must set zip_release: true and a filename ending in .zip")
    if "/" in name:
        raise ReleaseZipError(f"hacs.json filename must be a plain file name: {name}")
    return name


def package_files(package_dir: Path = PACKAGE_DIR) -> list[str]:
    """Return the tracked files under ``package_dir``, relative to it and sorted."""
    relative_dir = package_dir.relative_to(REPO_ROOT).as_posix()
    dirty = _git("status", "--porcelain", "--untracked-files=no", "--", relative_dir)
    if dirty.strip():
        raise ReleaseZipError(f"Tracked files under {relative_dir} differ from HEAD:\n{dirty.rstrip()}")

    names: list[str] = []
    for tracked in _git("ls-files", "-z", "--", relative_dir).split("\0"):
        if not tracked:
            continue
        name = PurePosixPath(tracked).relative_to(relative_dir).as_posix()
        parts = PurePosixPath(name).parts
        if any(part.startswith(".") for part in parts):
            continue
        if "__pycache__" in parts or name.endswith(BYTECODE_SUFFIXES):
            raise ReleaseZipError(f"Bytecode is tracked in Git: {name}")
        path = package_dir / name
        if path.is_symlink():
            raise ReleaseZipError(f"Symbolic links are not allowed: {name}")
        if not path.is_file():
            raise ReleaseZipError(f"Tracked file is missing from the checkout: {name}")
        names.append(name)
    return sorted(names)


def check_frontend_imports(package_dir: Path, members: set[str]) -> list[str]:
    """Follow the card bundle's imports and fail on any module the zip would not hold.

    Returns the JavaScript modules reached from the entry bundle, in visit order.
    """
    visited: list[str] = []
    pending = [FRONTEND_ENTRY]
    while pending:
        name = pending.pop()
        if name in visited:
            continue  # the entry and the lazily loaded map chunk import each other
        visited.append(name)
        source = (package_dir / name).read_text(encoding="utf-8")
        for match in JS_DYNAMIC_IMPORT.finditer(source):
            literal = JS_IMPORT.match(source, match.start())
            if not match.group(1) or literal is None or "${" in literal.group(2):
                raise ReleaseZipError(f"{name} has a computed import() the build cannot check")
        for _quote, specifier in JS_IMPORT.findall(source):
            if not specifier.startswith(("./", "../")):
                raise ReleaseZipError(f"{name} imports {specifier!r}, which is not a relative module")
            target = posixpath.normpath((PurePosixPath(name).parent / specifier).as_posix())
            if target not in members:
                raise ReleaseZipError(f"{name} imports {specifier}, which is not in the package")
            pending.append(target)
    return visited


def check_members(package_dir: Path, names: Sequence[str]) -> None:
    """Fail unless the file list loads as the integration with working dashboard cards."""
    members = set(names)
    missing = [required for required in REQUIRED_FILES if required not in members]
    if missing:
        raise ReleaseZipError(f"Missing from the package: {', '.join(missing)}")
    reached = check_frontend_imports(package_dir, members)
    bundles = {name for name in names if name.startswith("frontend/") and name.endswith(".js")}
    if unreached := sorted(bundles - set(reached)):
        raise ReleaseZipError(f"Stale frontend bundles nothing imports: {', '.join(unreached)}")


def source_date_epoch(environ: Mapping[str, str] | None = None) -> int:
    """Return the entry timestamp: ``SOURCE_DATE_EPOCH``, else the ``HEAD`` commit time."""
    value = (os.environ if environ is None else environ).get("SOURCE_DATE_EPOCH") or _git(
        "log", "-1", "--format=%ct", "HEAD"
    ).strip()
    try:
        epoch = int(value)
    except ValueError as err:
        raise ReleaseZipError(f"Invalid SOURCE_DATE_EPOCH: {value!r}") from err
    return max(epoch, ZIP_EPOCH)


def check_version(package_dir: Path, expected: str) -> None:
    """Fail when the ``manifest.json`` version differs from the release ``expected``."""
    manifest = json.loads((package_dir / "manifest.json").read_text(encoding="utf-8"))
    actual = manifest.get("version")
    if actual != expected.removeprefix("v"):
        raise ReleaseZipError(f"manifest.json version {actual} does not match release {expected}")


def build_zip(package_dir: Path, zip_path: Path, epoch: int) -> list[str]:
    """Write the reproducible zip and return its entry names in order."""
    names = package_files(package_dir)
    check_members(package_dir, names)
    date_time = time.gmtime(epoch)[:6]
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "w") as archive:
        for name in names:
            info = zipfile.ZipInfo(name, date_time=date_time)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3  # Unix, so external_attr holds the file mode
            info.external_attr = FILE_MODE << 16
            archive.writestr(info, (package_dir / name).read_bytes(), compresslevel=COMPRESS_LEVEL)
    return names


def write_checksums(output_dir: Path, file_names: Sequence[str]) -> Path:
    """Write ``SHA256SUMS`` in the format ``sha256sum -c`` reads."""
    lines = [f"{hashlib.sha256((output_dir / name).read_bytes()).hexdigest()}  {name}\n" for name in file_names]
    checksums_path = output_dir / CHECKSUMS_NAME
    checksums_path.write_text("".join(lines), encoding="utf-8")
    return checksums_path


def build_release(output_dir: Path, *, version: str | None = None) -> Path:
    """Build the release zip and ``SHA256SUMS`` in ``output_dir``; return the zip path."""
    if version is not None:
        check_version(PACKAGE_DIR, version)
    name = zip_name()
    zip_path = output_dir / name
    build_zip(PACKAGE_DIR, zip_path, source_date_epoch())
    write_checksums(output_dir, [name])
    return zip_path


def main(argv: Sequence[str] | None = None) -> int:
    """Run the command-line interface."""
    parser = argparse.ArgumentParser(description="Build the reproducible release zip.")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=REPO_ROOT / "dist",
        help="directory for the zip and SHA256SUMS (default: dist)",
    )
    parser.add_argument("--version", help="release version or tag (v2026.10.1); fail if manifest.json differs")
    args = parser.parse_args(argv)

    try:
        zip_path = build_release(args.output_dir, version=args.version)
    except ReleaseZipError as err:
        print(f"Error: {err}", file=sys.stderr)
        return 1

    digest = hashlib.sha256(zip_path.read_bytes()).hexdigest()
    with zipfile.ZipFile(zip_path) as archive:
        count = len(archive.namelist())
    print(f"Built {zip_path} ({count} files, sha256 {digest})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
