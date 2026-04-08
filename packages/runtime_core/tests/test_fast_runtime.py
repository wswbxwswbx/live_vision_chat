import pytest

from runtime_core.session_task_registry import SessionTaskRegistry
from runtime_core.session_conversation_registry import SessionConversationRegistry
from runtime_store.memory_store import InMemoryRuntimeStore


@pytest.mark.asyncio
async def test_fast_runtime_initializes_conversation_on_first_turn() -> None:
    from runtime_core.fast_runtime import FastRuntime

    store = InMemoryRuntimeStore()
    registry = SessionConversationRegistry()
    task_registry = SessionTaskRegistry()
    runtime = FastRuntime(
        store=store,
        conversation_registry=registry,
        task_registry=task_registry,
    )

    result = await runtime.handle_turn(session_id="s1", text="你好")

    assert result.reply_text == "Fast reply: 你好"
    assert result.handoff_task_id is None
    assert registry.get_dialog_id("s1") == "s1"
    assert store.get_conversation("s1") == {
        "dialog_id": "s1",
        "speaker_owner": "fast",
        "attention_owner": "fast",
        "foreground_task_id": None,
        "background_task_ids": [],
        "interrupt_epoch": 0,
    }


@pytest.mark.asyncio
async def test_fast_runtime_preserves_existing_conversation_state() -> None:
    from runtime_core.fast_runtime import FastRuntime

    store = InMemoryRuntimeStore()
    registry = SessionConversationRegistry()
    task_registry = SessionTaskRegistry()
    registry.bind_dialog("s1", "dialog-1")
    store.upsert_conversation(
        "dialog-1",
        {
            "dialog_id": "dialog-1",
            "speaker_owner": "fast",
            "attention_owner": "slow",
            "foreground_task_id": "task-1",
            "background_task_ids": ["task-2"],
            "interrupt_epoch": 3,
        },
        actor="system",
    )
    runtime = FastRuntime(
        store=store,
        conversation_registry=registry,
        task_registry=task_registry,
    )

    result = await runtime.handle_turn(session_id="s1", text="继续")

    assert result.reply_text == "Fast reply: 继续"
    assert result.handoff_task_id is None
    assert registry.get_dialog_id("s1") == "dialog-1"
    assert store.get_conversation("dialog-1") == {
        "dialog_id": "dialog-1",
        "speaker_owner": "fast",
        "attention_owner": "slow",
        "foreground_task_id": "task-1",
        "background_task_ids": ["task-2"],
        "interrupt_epoch": 3,
    }


@pytest.mark.asyncio
async def test_fast_runtime_creates_handoff_for_reminder_turn() -> None:
    from runtime_core.fast_runtime import FastRuntime

    store = InMemoryRuntimeStore()
    registry = SessionConversationRegistry()
    task_registry = SessionTaskRegistry()
    runtime = FastRuntime(
        store=store,
        conversation_registry=registry,
        task_registry=task_registry,
    )

    result = await runtime.handle_turn(
        session_id="s1",
        text="Remind me tomorrow to pay rent",
    )

    assert result.reply_text == "I’ll handle that reminder in the background."
    assert result.handoff_task_id == "task-1"
    assert task_registry.list_task_ids("s1") == ["task-1"]

    created_task = store.get_task("task-1")
    assert created_task is not None
    assert created_task["dialog_id"] == "s1"
    assert created_task["status"] == "accepted"
    assert created_task["payload"]["task_type"] == "create_reminder"
    assert created_task["payload"]["raw_user_input"] == "Remind me tomorrow to pay rent"
