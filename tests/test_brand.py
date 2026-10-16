"""Brand images (#22): the integration ships exactly the artwork rendered from branding/."""

from __future__ import annotations

from pathlib import Path
import struct

ROOT = Path(__file__).parent.parent
BRANDING = ROOT / "branding"
BRAND = ROOT / "custom_components" / "ausnz_disaster_watch" / "brand"

# Home Assistant brands layout: square icons, logos 128/256 px high
EXPECTED = {
    "icon.png": (256, 256),
    "icon@2x.png": (512, 512),
    "logo.png": (None, 128),
    "logo@2x.png": (None, 256),
    "dark_logo.png": (None, 128),
    "dark_logo@2x.png": (None, 256),
}


def _png_size(path: Path) -> tuple[int, int]:
    header = path.read_bytes()[:24]
    assert header[:8] == b"\x89PNG\r\n\x1a\n", f"{path.name} is not a PNG"
    return struct.unpack(">II", header[16:24])


def test_brand_folder_matches_branding_exports() -> None:
    """brand/ holds exactly the PNGs rendered into branding/ by script/brand, byte for byte."""
    assert sorted(p.name for p in BRAND.iterdir()) == sorted(EXPECTED)
    for name in EXPECTED:
        assert (BRAND / name).read_bytes() == (BRANDING / name).read_bytes(), f"{name}: run script/brand"


def test_brand_image_sizes() -> None:
    """Icons are square at 256/512 px and logos 128/256 px high."""
    for name, (width, height) in EXPECTED.items():
        actual_width, actual_height = _png_size(BRAND / name)
        assert actual_height == height, name
        if width is not None:
            assert actual_width == width, name


def test_branding_has_only_masters_and_exports() -> None:
    """branding/ keeps the SVG masters and their PNG exports, nothing else."""
    masters = {"icon.svg", "logo.svg", "dark_logo.svg"}
    assert sorted(p.name for p in BRANDING.iterdir()) == sorted(masters | set(EXPECTED))
