import re
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Literal, Protocol
from uuid import UUID


@dataclass(frozen=True)
class StoreKey:
    project_id: UUID
    category: Literal["uploads", "glyphs", "artifacts"]
    name: str

    def __post_init__(self):
        if (
            not isinstance(self.project_id, UUID)
            or self.category not in {"uploads", "glyphs", "artifacts"}
            or not re.fullmatch(
                r"(?:[0-9a-f]{32}(\.[a-z0-9]{1,8})?|U\+[0-9A-F]{4,6}\.svg)", self.name
            )
        ):
            raise ValueError("Invalid object key")

    def __str__(self):
        return f"projects/{self.project_id}/{self.category}/{self.name}"


class ObjectStore(Protocol):
    def put(self, key: StoreKey, data: bytes, content_type: str) -> None: ...
    def get(self, key: StoreKey) -> bytes: ...
    def stream(self, key: StoreKey) -> Iterator[bytes]: ...
    def delete(self, key: StoreKey) -> None: ...
    def delete_prefix(self, project_id: UUID) -> int: ...
    def exists(self, key: StoreKey) -> bool: ...
