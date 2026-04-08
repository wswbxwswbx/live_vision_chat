import pytest

from runtime_store.models import ReminderCheckpointPayload, ReminderTaskPayload
from runtime_store.memory_store import InMemoryRuntimeStore


def _seed_conversation(store: InMemoryRuntimeStore, dialog_id: str = "dialog-1") -> None:
    store.upsert_conversation(
        dialog_id,
        {
            "dialog_id": dialog_id,
            "speaker_owner": "fast",
            "attention_owner": "fast",
            "foreground_task_id": None,
            "background_task_ids": [],
            "interrupt_epoch": 0,
        },
        actor="system",
    )


@pytest.mark.asyncio
async def test_accept_attaches_task_to_background_and_sets_attention_slow() -> None:
    from runtime_core.task_runtime import TaskRuntime

    store = InMemoryRuntimeStore()
    _seed_conversation(store)
    task_runtime = TaskRuntime(store=store)

    await task_runtime.accept(task_id="task-1", dialog_id="dialog-1")

    conversation = store.get_conversation("dialog-1")

    assert conversation is not None
    assert conversation["attention_owner"] == "slow"
    assert "task-1" in conversation["background_task_ids"]
    assert store.get_task("task-1") == {
        "task_id": "task-1",
        "dialog_id": "dialog-1",
        "status": "accepted",
    }


@pytest.mark.asyncio
async def test_slow_runtime_run_once_completes_and_detaches_task() -> None:
    from runtime_core.slow_runtime import SlowRuntime

    store = InMemoryRuntimeStore()
    _seed_conversation(store)
    runtime = SlowRuntime(store=store)

    result = await runtime.run_once(task_id="task-1", dialog_id="dialog-1")

    conversation = store.get_conversation("dialog-1")
    task = store.get_task("task-1")

    assert result.task_id == "task-1"
    assert result.status == "completed"
    assert conversation is not None
    assert conversation["attention_owner"] == "fast"
    assert conversation["background_task_ids"] == []
    assert task == {
        "task_id": "task-1",
        "dialog_id": "dialog-1",
        "status": "completed",
    }


@pytest.mark.asyncio
async def test_accept_rejects_rebinding_task_to_another_dialog() -> None:
    from runtime_core.task_runtime import TaskRuntime

    store = InMemoryRuntimeStore()
    _seed_conversation(store, "dialog-1")
    _seed_conversation(store, "dialog-2")
    store.upsert_task(
        "task-1",
        {
            "task_id": "task-1",
            "dialog_id": "dialog-1",
            "status": "accepted",
        },
    )
    task_runtime = TaskRuntime(store=store)

    with pytest.raises(ValueError, match="belongs to dialog"):
        await task_runtime.accept(task_id="task-1", dialog_id="dialog-2")


@pytest.mark.asyncio
async def test_complete_can_preserve_attention_when_requested() -> None:
    from runtime_core.task_runtime import TaskRuntime

    store = InMemoryRuntimeStore()
    _seed_conversation(store)
    task_runtime = TaskRuntime(store=store)

    await task_runtime.accept(task_id="task-1", dialog_id="dialog-1")
    await task_runtime.complete(
        task_id="task-1",
        dialog_id="dialog-1",
        release_attention=False,
    )

    conversation = store.get_conversation("dialog-1")

    assert conversation is not None
    assert conversation["attention_owner"] == "slow"
    assert conversation["background_task_ids"] == []


@pytest.mark.asyncio
async def test_mark_waiting_user_updates_task_and_checkpoint() -> None:
    from runtime_core.task_runtime import TaskRuntime

    store = InMemoryRuntimeStore()
    _seed_conversation(store)
    task_runtime = TaskRuntime(store=store)

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

    await task_runtime.accept(
        task_id="task-1",
        dialog_id="dialog-1",
        payload=task_payload,
        summary="create_reminder",
    )
    await task_runtime.mark_waiting_user(
        task_id="task-1",
        dialog_id="dialog-1",
        summary="When should I remind you?",
        checkpoint_payload=checkpoint_payload,
    )

    task = store.get_task("task-1")
    checkpoint = store.get_checkpoint("task-1")
    events = store.list_task_events("task-1")

    assert task is not None
    assert task["status"] == "waiting_user"
    assert task["summary"] == "When should I remind you?"
    assert checkpoint is not None
    assert checkpoint["state"] == "waiting_user"
    assert checkpoint["payload"]["missing_field"] == "scheduled_at"
    assert [event["event_kind"] for event in events] == ["accepted", "waiting_user"]


@pytest.mark.asyncio
async def test_mark_failed_updates_task_and_releases_attention() -> None:
    from runtime_core.task_runtime import TaskRuntime

    store = InMemoryRuntimeStore()
    _seed_conversation(store)
    task_runtime = TaskRuntime(store=store)

    await task_runtime.accept(task_id="task-1", dialog_id="dialog-1")
    await task_runtime.mark_failed(
        task_id="task-1",
        dialog_id="dialog-1",
        summary="Failed to create reminder",
    )

    task = store.get_task("task-1")
    conversation = store.get_conversation("dialog-1")
    events = store.list_task_events("task-1")

    assert task is not None
    assert task["status"] == "failed"
    assert task["summary"] == "Failed to create reminder"
    assert conversation is not None
    assert conversation["attention_owner"] == "fast"
    assert conversation["background_task_ids"] == []
    assert [event["event_kind"] for event in events] == ["accepted", "failed"]
