from memory.in_memory_memory_system import InMemoryMemorySystem


def test_memory_system_stores_and_retrieves_entries() -> None:
    memory = InMemoryMemorySystem()
    entry = memory.write("user", "likes espresso", tags=["coffee"])

    hits = memory.search("espresso")

    assert hits == [entry]


def test_memory_system_search_can_filter_by_namespace() -> None:
    memory = InMemoryMemorySystem()
    user_entry = memory.write("user", "likes espresso", tags=["coffee"])
    memory.write("project", "espresso machine issue", tags=["coffee"])

    hits = memory.search("espresso", namespace="user")

    assert hits == [user_entry]
