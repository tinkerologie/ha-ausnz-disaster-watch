#!/usr/bin/env python3
"""Write the requirements the integration declares, plus Home Assistant's constraints.

Reads the integration's manifest and the manifests of the Home Assistant components
it lists in ``dependencies``/``after_dependencies`` or provides platforms for
(resolved transitively), from the ``homeassistant`` package installed in the running
interpreter. Writes their requirements, one per line, to REQUIREMENTS and that
release's ``package_constraints.txt`` to CONSTRAINTS. Extra COMPONENTs (such as the
ones the tests set up) are resolved the same way. Used by ``script/check-imports``
and the HA Next workflow.

Usage: python script/declared_requirements.py REQUIREMENTS CONSTRAINTS [COMPONENT ...]
"""

from __future__ import annotations

import json
from pathlib import Path
import sys

import homeassistant

DOMAIN = "ausnz_disaster_watch"
REPO_ROOT = Path(__file__).resolve().parent.parent


def main(reqs_path: str, constraints_path: str, extra_components: list[str]) -> None:
    """Resolve the declared requirements and write both files."""
    ha_root = Path(homeassistant.__file__).parent
    package = REPO_ROOT / "custom_components" / DOMAIN
    own = json.loads((package / "manifest.json").read_text())

    requirements = list(own.get("requirements", []))
    seen: set[str] = set()
    queue = list(own.get("dependencies", [])) + list(own.get("after_dependencies", [])) + extra_components
    # Entity platform modules (sensor.py, camera.py, ...) make Home Assistant load that
    # component too, which installs its requirements.
    queue += [
        path.stem for path in package.glob("*.py") if (ha_root / "components" / path.stem / "manifest.json").exists()
    ]
    while queue:
        component = queue.pop()
        if component in seen:
            continue
        seen.add(component)
        manifest = ha_root / "components" / component / "manifest.json"
        if not manifest.exists():
            continue
        data = json.loads(manifest.read_text())
        requirements.extend(data.get("requirements", []))
        # Home Assistant also sets up after_dependencies that are present (e.g. sensor -> recorder)
        queue.extend(data.get("dependencies", []))
        queue.extend(data.get("after_dependencies", []))

    Path(reqs_path).write_text("\n".join(dict.fromkeys(requirements)) + "\n")
    Path(constraints_path).write_text((ha_root / "package_constraints.txt").read_text())
    print(f"Integration requirements: {own.get('requirements', [])}")
    print(f"Component dependencies resolved: {sorted(seen)}")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2], sys.argv[3:])
