from typing import Protocol


class Storage(Protocol):
    """Byte storage for original and derived files.

    Keys are slash-separated and treated as immutable: callers never overwrite
    an existing key with different content.
    """

    def put(self, key: str, data: bytes) -> None: ...

    def get(self, key: str) -> bytes: ...

    def exists(self, key: str) -> bool: ...

    def delete(self, key: str) -> None: ...


class StorageKeyError(ValueError):
    """The key is empty, absolute, or escapes the storage root."""


class StorageNotFoundError(FileNotFoundError):
    """No object exists under the requested key."""
