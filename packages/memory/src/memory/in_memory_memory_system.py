from __future__ import annotations

from .interfaces import MemoryEntry


class InMemoryMemorySystem:
    def __init__(self) -> None:
        self._entries: list[MemoryEntry] = []
        self._next_id = 1

    def write(
        self,
        namespace: str,
        content: str,
        tags: list[str] | None = None,
    ) -> MemoryEntry:
        entry = MemoryEntry(
            entry_id=f"mem-{self._next_id}",
            namespace=namespace,
            content=content,
            tags=list(tags or []),
        )
        self._next_id += 1
        self._entries.append(entry)
        return entry

    def search(
        self,
        query: str,
        namespace: str | None = None,
    ) -> list[MemoryEntry]:
        normalized_query = query.casefold()
        results: list[MemoryEntry] = []
        for entry in self._entries:
            if namespace is not None and entry.namespace != namespace:
                continue

            haystack = " ".join([entry.content, *entry.tags]).casefold()
            if normalized_query in haystack:
                results.append(entry)

        return results
