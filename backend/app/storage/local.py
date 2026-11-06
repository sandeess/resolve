import os
import tempfile
from pathlib import Path

from app.storage.base import StorageKeyError, StorageNotFoundError


class LocalStorage:
    """`Storage` backed by a directory on a local volume."""

    def __init__(self, root: Path) -> None:
        self._root = root.resolve()
        self._root.mkdir(parents=True, exist_ok=True)

    def put(self, key: str, data: bytes) -> None:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        # Write to a temp file first so readers never see a partial object.
        fd, tmp_name = tempfile.mkstemp(dir=path.parent)
        try:
            with os.fdopen(fd, "wb") as tmp:
                tmp.write(data)
            os.replace(tmp_name, path)
        except BaseException:
            Path(tmp_name).unlink(missing_ok=True)
            raise

    def get(self, key: str) -> bytes:
        try:
            return self._path(key).read_bytes()
        except FileNotFoundError as exc:
            raise StorageNotFoundError(key) from exc

    def exists(self, key: str) -> bool:
        return self._path(key).is_file()

    def delete(self, key: str) -> None:
        self._path(key).unlink(missing_ok=True)

    def _path(self, key: str) -> Path:
        if not key or key.startswith(("/", "\\")):
            raise StorageKeyError(f"invalid storage key: {key!r}")
        path = (self._root / key).resolve()
        if not path.is_relative_to(self._root):
            raise StorageKeyError(f"storage key escapes root: {key!r}")
        return path
