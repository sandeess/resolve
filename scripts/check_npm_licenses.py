"""Fail if a production npm dependency of the frontend has a strong-copyleft licence.

Reads each installed package's own package.json (no extra downloads). Same policy as
backend/scripts/check_licenses.py. For SPDX "A OR B" expressions the package is fine
if any alternative is acceptable.

Usage (from the repo root, after `npm ci`):  python scripts/check_npm_licenses.py
"""

import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend" / "scripts"))

from check_licenses import is_strong_copyleft  # noqa: E402

# Packages whose licence field is missing or non-standard, checked by hand.
REVIEWED: dict[str, str] = {}


def licence_of(manifest: dict[str, object]) -> str:
    value = manifest.get("license") or manifest.get("licenses") or ""
    if isinstance(value, dict):
        return str(value.get("type", ""))
    if isinstance(value, list):
        return " OR ".join(str(v.get("type", "")) if isinstance(v, dict) else str(v) for v in value)
    return str(value)


def acceptable(licence: str) -> bool:
    if not licence or licence.upper() in ("UNKNOWN", "UNLICENSED"):
        return False
    alternatives = re.split(r"\s+OR\s+", licence.strip("() "), flags=re.IGNORECASE)
    return any(not is_strong_copyleft(a) for a in alternatives)


def main() -> int:
    listing = subprocess.run(
        ["npm", "ls", "--omit=dev", "--all", "--parseable", "--workspace", "frontend"],
        capture_output=True, text=True, check=False, shell=sys.platform == "win32",
    ).stdout
    paths = sorted({Path(line) for line in listing.splitlines() if line.strip()})
    problems = []
    for path in paths:
        manifest_path = path / "package.json"
        if not manifest_path.is_file() or path.name == "frontend" and path.parent.name == "resolve":
            continue
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        name = str(manifest.get("name", path.name))
        if manifest.get("private") or name in REVIEWED:
            continue
        licence = licence_of(manifest)
        if not acceptable(licence):
            problems.append(f"{name}@{manifest.get('version', '?')}: {licence or 'no licence declared'}")
    for message in problems:
        sys.stderr.write(f"LICENCE VIOLATION (shipped): {message}\n")
    sys.stdout.write(f"checked {len(paths)} production npm packages: {len(problems)} violation(s)\n")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
