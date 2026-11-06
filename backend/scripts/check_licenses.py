"""Fail the build if a shipped dependency carries a strong-copyleft or unknown licence.

Policy: permissive licences (MIT, BSD, Apache-2.0, ISC, PSF, ...) and weak copyleft
used unmodified (LGPL, MPL) are fine. GPL, AGPL and SSPL are not, because shipping
the app would then oblige us to publish it. A package whose licence cannot be read
must be reviewed by hand and listed in `REVIEWED` with a reason.

Usage (from backend/):

    uv export --no-dev --no-hashes --no-emit-project > /tmp/prod.txt
    uv run python scripts/check_licenses.py /tmp/prod.txt

Dev-only tools are checked too but only warn: they are not shipped.
"""

import json
import re
import subprocess
import sys
from collections.abc import Iterable
from pathlib import Path

# GPL/AGPL/SSPL, but not LGPL ("(?<!L)GPL") and not "Lesser General Public".
_STRONG = re.compile(r"(?<!L)GPL|AGPL|SSPL|Affero", re.IGNORECASE)

# Packages whose licence field is unreadable, checked by hand. name -> reason.
REVIEWED: dict[str, str] = {"app": "this project"}


def canonical(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def is_strong_copyleft(licence: str) -> bool:
    if "Lesser" in licence:
        return False
    return bool(_STRONG.search(licence)) or "General Public License" in licence


def violations(
    packages: Iterable[dict[str, str]], only: set[str] | None = None
) -> list[str]:
    """One message per offending package; `only` limits the check to those names."""
    problems = []
    for package in packages:
        name, licence = package["Name"], package["License"]
        if only is not None and canonical(name) not in only:
            continue
        if canonical(name) in REVIEWED:
            continue
        if licence in ("", "UNKNOWN"):
            problems.append(
                f"{name} {package['Version']}: licence unknown (review it, then add to REVIEWED)"
            )
        elif is_strong_copyleft(licence):
            problems.append(f"{name} {package['Version']}: {licence}")
    return problems


def shipped_packages(requirements: str) -> set[str]:
    """Package names from `uv export` output (lines like `name==1.2.3 ; marker`)."""
    return {
        canonical(m.group(1))
        for line in requirements.splitlines()
        if (m := re.match(r"([A-Za-z0-9_.-]+)==", line))
    }


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        sys.stderr.write(__doc__ or "")
        return 2
    shipped = shipped_packages(Path(argv[1]).read_text())
    listing = subprocess.run(
        [sys.executable, "-m", "piplicenses", "--format=json"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    packages = json.loads(listing)
    errors = violations(packages, only=shipped)
    warnings = [m for m in violations(packages) if m not in errors]
    for message in errors:
        sys.stderr.write(f"LICENCE VIOLATION (shipped): {message}\n")
    for message in warnings:
        sys.stderr.write(f"licence warning (dev only): {message}\n")
    sys.stdout.write(
        f"checked {len(shipped)} shipped packages: {len(errors)} violation(s)\n"
    )
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
