import pytest

from runtime_core.session_conversation_registry import SessionConversationRegistry
from runtime_store.memory_store import InMemoryRuntimeStore


@pytest.mark.asyncio
async def test_fast_runtime_initializes_conversation_on_first_turn() -> None:
    from runtime_core.fast_runtime import FastRuntime

    store = InMemoryRuntimeStore()
    registry = SessionConversationRegistry()
    runtime = FastRuntime(store=store, conversation_registry=registry)

    result = await runtime.handle_turn(session_id="s1", text="你好")

    assert result.reply_text == "stub"
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
    runtime = FastRuntime(store=store, conversation_registry=registry)

    await runtime.handle_turn(session_id="s1", text="继续")

    assert registry.get_dialog_id("s1") == "dialog-1"
    assert store.get_conversation("dialog-1") == {
        "dialog_id": "dialog-1",
        "speaker_owner": "fast",
        "attention_owner": "slow",
        "foreground_task_id": "task-1",
        "background_task_ids": ["task-2"],
        "interrupt_epoch": 3,
    }
