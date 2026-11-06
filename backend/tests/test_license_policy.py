import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from check_licenses import is_strong_copyleft, violations  # noqa: E402


@pytest.mark.parametrize(
    ("licence", "strong"),
    [
        ("MIT", False),
        ("Apache-2.0", False),
        ("BSD-3-Clause", False),
        ("MPL-2.0", False),
        ("LGPL-3.0-only", False),
        ("GNU Lesser General Public License v3 (LGPLv3)", False),
        ("GPL-3.0-only", True),
        ("GNU General Public License v3 (GPLv3)", True),
        ("AGPL-3.0", True),
        ("GNU Affero General Public License v3", True),
        ("SSPL-1.0", True),
    ],
)
def test_strong_copyleft_detection(licence: str, strong: bool) -> None:
    assert is_strong_copyleft(licence) is strong


def _pkg(name: str, licence: str) -> dict[str, str]:
    return {"Name": name, "Version": "1.0", "License": licence}


def test_violations_flag_strong_copyleft_and_unknown_but_allow_lgpl_and_reviewed() -> (
    None
):
    packages = [
        _pkg("fine", "MIT"),
        _pkg("psycopg", "LGPL-3.0-only"),
        _pkg("pymupdf", "AGPL-3.0"),
        _pkg("mystery", "UNKNOWN"),
        _pkg("app", "UNKNOWN"),
    ]
    messages = violations(packages)
    assert [m.split()[0] for m in messages] == ["pymupdf", "mystery"]


def test_dev_only_packages_can_be_excluded() -> None:
    packages = [_pkg("shipped", "MIT"), _pkg("devtool", "GPL-3.0-only")]
    assert violations(packages, only={"shipped"}) == []
