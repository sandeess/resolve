from pathlib import Path

import pytest

from app.storage.base import StorageKeyError, StorageNotFoundError
from app.storage.local import LocalStorage


def test_round_trip(tmp_path: Path) -> None:
    storage = LocalStorage(tmp_path)
    storage.put("journal/1/doc/v1/abc", b"hello")
    assert storage.exists("journal/1/doc/v1/abc")
    assert storage.get("journal/1/doc/v1/abc") == b"hello"
    storage.delete("journal/1/doc/v1/abc")
    assert not storage.exists("journal/1/doc/v1/abc")


def test_missing_key_raises(tmp_path: Path) -> None:
    with pytest.raises(StorageNotFoundError):
        LocalStorage(tmp_path).get("nope")


@pytest.mark.parametrize("key", ["", "/etc/passwd", "../outside", "a/../../outside"])
def test_rejects_unsafe_keys(tmp_path: Path, key: str) -> None:
    with pytest.raises(StorageKeyError):
        LocalStorage(tmp_path).put(key, b"x")
