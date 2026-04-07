from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class MemoryEntry:
    entry_id: str
    namespace: str
    content: str
    tags: list[str]


class MemorySystem(Protocol):
    def write(
        self,
        namespace: str,
        content: str,
        tags: list[str] | None = None,
    ) -> MemoryEntry: ...

    def search(
        self,
        query: str,
        namespace: str | None = None,
    ) -> list[MemoryEntry]: ...
