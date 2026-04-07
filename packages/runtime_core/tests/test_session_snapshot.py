from runtime_core.session_conversation_registry import SessionConversationRegistry
from runtime_core.session_snapshot import SessionSnapshotReader
from runtime_core.session_task_registry import SessionTaskRegistry
from runtime_store.memory_store import InMemoryRuntimeStore


def test_snapshot_collects_conversation_tasks_and_tool_calls() -> None:
    store = InMemoryRuntimeStore()
    conversation_registry = SessionConversationRegistry()
    task_registry = SessionTaskRegistry()
    reader = SessionSnapshotReader(
        store=store,
        conversation_registry=conversation_registry,
        task_registry=task_registry,
    )

    conversation_registry.bind_dialog("session-1", "dialog-1")
    task_registry.bind_task("session-1", "task-1")

    conversation = store.upsert_conversation(
        "dialog-1",
        {
            "dialog_id": "dialog-1",
            "speaker_owner": "fast",
            "attention_owner": "slow",
            "foreground_task_id": "task-1",
            "background_task_ids": [],
            "interrupt_epoch": 2,
        },
        actor="system",
    )
    task = store.upsert_task(
        "task-1",
        {
            "dialog_id": "dialog-1",
            "status": "running",
            "summary": "Inspect the cable",
            "payload": {"step": "inspect"},
        },
    )
    checkpoint = store.upsert_checkpoint(
        "task-1",
        {
            "dialog_id": "dialog-1",
            "state": "waiting_user",
            "payload": {"cursor": "step-2"},
        },
    )
    event = store.append_task_event(
        "task-1",
        {
            "dialog_id": "dialog-1",
            "event_kind": "progress",
            "summary": "Waiting for user confirmation",
            "payload": {"percent": 50},
        },
    )
    tool_call = store.upsert_tool_call(
        "call-1",
        {
            "task_id": "task-1",
            "status": "completed",
            "tool_name": "camera_capture",
            "payload": {"frame_id": "frame-1"},
        },
    )

    snapshot = reader.get_session_snapshot("session-1")

    assert snapshot is not None
    assert snapshot.session_id == "session-1"
    assert snapshot.dialog_id == "dialog-1"
    assert snapshot.conversation == conversation
    assert len(snapshot.tasks) == 1
    assert snapshot.tasks[0].task == task
    assert snapshot.tasks[0].checkpoint == checkpoint
    assert snapshot.tasks[0].events == [event]
    assert snapshot.tasks[0].tool_calls == [tool_call]


def test_task_registry_supports_bidirectional_lookup() -> None:
    registry = SessionTaskRegistry()

    registry.bind_task("session-1", "task-1")
    registry.bind_task("session-1", "task-2")
    registry.bind_task("session-1", "task-1")

    assert registry.get_session_id("task-1") == "session-1"
    assert registry.get_session_id("task-2") == "session-1"
    assert registry.list_task_ids("session-1") == ["task-1", "task-2"]


def test_snapshot_ignores_stale_task_references_without_store_records() -> None:
    store = InMemoryRuntimeStore()
    conversation_registry = SessionConversationRegistry()
    task_registry = SessionTaskRegistry()
    reader = SessionSnapshotReader(
        store=store,
        conversation_registry=conversation_registry,
        task_registry=task_registry,
    )

    conversation_registry.bind_dialog("session-1", "dialog-1")
    task_registry.bind_task("session-1", "task-stale")

    store.upsert_conversation(
        "dialog-1",
        {
            "dialog_id": "dialog-1",
            "speaker_owner": "fast",
            "attention_owner": "slow",
            "foreground_task_id": "task-stale",
            "background_task_ids": ["task-stale-2"],
            "interrupt_epoch": 0,
        },
        actor="system",
    )

    snapshot = reader.get_session_snapshot("session-1")

    assert snapshot is not None
    assert snapshot.tasks == []
