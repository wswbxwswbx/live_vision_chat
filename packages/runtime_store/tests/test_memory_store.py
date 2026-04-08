import pytest

from runtime_store.memory_store import InMemoryRuntimeStore
from runtime_store.models import ReminderCheckpointPayload, ReminderTaskPayload


def test_slow_cannot_change_speaker_owner() -> None:
    store = InMemoryRuntimeStore()

    store.upsert_conversation(
        "dialog-1",
        {
            "dialog_id": "dialog-1",
            "speaker_owner": "fast",
            "attention_owner": "fast",
            "foreground_task_id": None,
            "background_task_ids": [],
            "interrupt_epoch": 0,
        },
        actor="system",
    )

    with pytest.raises(ValueError, match="speaker_owner"):
        store.upsert_conversation("dialog-1", {"speaker_owner": "slow"}, actor="slow")


def test_interrupt_epoch_cannot_go_backwards() -> None:
    store = InMemoryRuntimeStore()

    store.upsert_conversation(
        "dialog-1",
        {
            "dialog_id": "dialog-1",
            "speaker_owner": "fast",
            "attention_owner": "fast",
            "foreground_task_id": None,
            "background_task_ids": [],
            "interrupt_epoch": 3,
        },
        actor="system",
    )

    with pytest.raises(ValueError, match="interrupt_epoch"):
        store.upsert_conversation("dialog-1", {"interrupt_epoch": 2}, actor="system")


def test_foreground_task_cannot_appear_in_background() -> None:
    store = InMemoryRuntimeStore()

    with pytest.raises(ValueError, match="foreground_task_id"):
        store.upsert_conversation(
            "dialog-1",
            {
                "dialog_id": "dialog-1",
                "speaker_owner": "fast",
                "attention_owner": "fast",
                "foreground_task_id": "task-1",
                "background_task_ids": ["task-1"],
                "interrupt_epoch": 0,
            },
            actor="system",
        )


def test_background_task_ids_must_be_unique() -> None:
    store = InMemoryRuntimeStore()

    with pytest.raises(ValueError, match="background_task_ids"):
        store.upsert_conversation(
            "dialog-1",
            {
                "dialog_id": "dialog-1",
                "speaker_owner": "fast",
                "attention_owner": "fast",
                "foreground_task_id": None,
                "background_task_ids": ["task-1", "task-1"],
                "interrupt_epoch": 0,
            },
            actor="system",
        )


def test_multi_conversation_state_is_independent() -> None:
    store = InMemoryRuntimeStore()

    first = store.upsert_conversation(
        "dialog-1",
        {
            "dialog_id": "dialog-1",
            "speaker_owner": "fast",
            "attention_owner": "fast",
            "foreground_task_id": "task-a",
            "background_task_ids": ["task-b"],
            "interrupt_epoch": 1,
        },
        actor="system",
    )
    second = store.upsert_conversation(
        "dialog-2",
        {
            "dialog_id": "dialog-2",
            "speaker_owner": "user",
            "attention_owner": "slow",
            "foreground_task_id": None,
            "background_task_ids": [],
            "interrupt_epoch": 0,
        },
        actor="system",
    )

    assert first["dialog_id"] == "dialog-1"
    assert second["dialog_id"] == "dialog-2"
    assert store.get_conversation("dialog-1") == first
    assert store.get_conversation("dialog-2") == second
    assert store.get_conversation("dialog-1") != store.get_conversation("dialog-2")


def test_upsert_and_get_task_round_trip() -> None:
    store = InMemoryRuntimeStore()

    created = store.upsert_task(
        "task-1",
        {
            "dialog_id": "dialog-1",
            "status": "running",
            "summary": "in progress",
            "payload": {"steps": [{"name": "capture"}]},
        },
    )

    assert created["task_id"] == "task-1"
    assert store.get_task("task-1") == created


def test_upsert_and_get_checkpoint_round_trip() -> None:
    store = InMemoryRuntimeStore()

    created = store.upsert_checkpoint(
        "task-1",
        {
            "dialog_id": "dialog-1",
            "state": "paused",
            "payload": {"cursor": {"step": 2}},
        },
    )

    assert created["task_id"] == "task-1"
    assert store.get_checkpoint("task-1") == created


def test_store_preserves_waiting_user_task_and_checkpoint_payload() -> None:
    store = InMemoryRuntimeStore()
    store.upsert_conversation(
        "dialog-1",
        {
            "dialog_id": "dialog-1",
            "speaker_owner": "fast",
            "attention_owner": "fast",
            "foreground_task_id": None,
            "background_task_ids": [],
            "interrupt_epoch": 0,
        },
        actor="system",
    )

    task_payload: ReminderTaskPayload = {
        "task_type": "create_reminder",
        "title": "Pay rent",
        "raw_user_input": "Remind me to pay rent",
        "scheduled_at_text": None,
    }
    checkpoint_payload: ReminderCheckpointPayload = {
        "task_type": "create_reminder",
        "title": "Pay rent",
        "raw_user_input": "Remind me to pay rent",
        "scheduled_at_text": None,
        "missing_field": "scheduled_at",
    }

    store.upsert_task(
        "task-1",
        {
            "dialog_id": "dialog-1",
            "status": "waiting_user",
            "payload": task_payload,
        },
    )
    store.upsert_checkpoint(
        "task-1",
        {
            "dialog_id": "dialog-1",
            "state": "waiting_user",
            "payload": checkpoint_payload,
        },
    )

    assert store.get_task("task-1")["status"] == "waiting_user"
    assert store.get_task("task-1")["payload"]["task_type"] == "create_reminder"
    assert store.get_checkpoint("task-1")["payload"]["missing_field"] == "scheduled_at"


def test_checkpoint_payload_mutation_does_not_leak_across_store_boundary() -> None:
    store = InMemoryRuntimeStore()
    payload: ReminderCheckpointPayload = {
        "task_type": "create_reminder",
        "title": "Pay rent",
        "raw_user_input": "Remind me to pay rent",
        "scheduled_at_text": None,
        "missing_field": "scheduled_at",
    }

    created = store.upsert_checkpoint(
        "task-1",
        {
            "dialog_id": "dialog-1",
            "state": "waiting_user",
            "payload": payload,
        },
    )

    payload["title"] = "Mutated"
    created["payload"]["title"] = "Mutated after read"

    stored = store.get_checkpoint("task-1")

    assert stored is not None
    assert stored["payload"]["title"] == "Pay rent"


def test_append_and_list_task_events_round_trip() -> None:
    store = InMemoryRuntimeStore()

    first = store.append_task_event(
        "task-1",
        {
            "dialog_id": "dialog-1",
            "event_kind": "accepted",
            "summary": "task accepted",
            "payload": {"progress": [0]},
        },
    )
    second = store.append_task_event(
        "task-1",
        {
            "dialog_id": "dialog-1",
            "event_kind": "progress",
            "summary": "task progressing",
            "payload": {"progress": [50]},
        },
    )

    assert store.list_task_events("task-1") == [first, second]


def test_upsert_and_get_tool_call_round_trip() -> None:
    store = InMemoryRuntimeStore()

    created = store.upsert_tool_call(
        "call-1",
        {
            "task_id": "task-1",
            "status": "running",
            "tool_name": "camera_capture",
            "payload": {"frames": [{"id": "frame-1"}]},
        },
    )

    assert created["call_id"] == "call-1"
    assert store.get_tool_call("call-1") == created


def test_nested_payload_mutation_does_not_leak_across_store_boundary() -> None:
    store = InMemoryRuntimeStore()
    payload = {"steps": [{"status": "queued"}], "meta": {"attempts": [1]}}

    created = store.upsert_task(
        "task-1",
        {
            "dialog_id": "dialog-1",
            "status": "running",
            "summary": "nested payload",
            "payload": payload,
        },
    )

    payload["steps"][0]["status"] = "mutated-after-write"
    payload["meta"]["attempts"].append(2)
    created["payload"]["steps"][0]["status"] = "mutated-after-read"
    created["payload"]["meta"]["attempts"].append(3)

    stored = store.get_task("task-1")

    assert stored is not None
    assert stored["payload"] == {"steps": [{"status": "queued"}], "meta": {"attempts": [1]}}
