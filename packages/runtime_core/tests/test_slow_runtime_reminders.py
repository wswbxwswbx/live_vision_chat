import pytest

from runtime_core.reminder_classifier import ReminderIntent, RuleBasedReminderClassifier
from runtime_core.reminder_parser import parse_reminder_request
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


def test_rule_based_classifier_detects_reminder_turn() -> None:
    classifier = RuleBasedReminderClassifier()

    assert classifier.classify("Remind me tomorrow to pay rent") == ReminderIntent.CREATE_REMINDER


def test_rule_based_classifier_detects_non_reminder_turn() -> None:
    classifier = RuleBasedReminderClassifier()

    assert classifier.classify("What time is it?") == ReminderIntent.NON_REMINDER


def test_reminder_parser_extracts_title_and_optional_time() -> None:
    parsed = parse_reminder_request("Remind me tomorrow at 9am to pay rent")

    assert parsed.title == "pay rent"
    assert parsed.scheduled_at_text == "tomorrow at 9am"


def test_reminder_parser_leaves_time_empty_when_missing() -> None:
    parsed = parse_reminder_request("Remind me to pay rent")

    assert parsed.title == "pay rent"
    assert parsed.scheduled_at_text is None


@pytest.mark.asyncio
async def test_slow_runtime_completes_reminder_when_time_is_present() -> None:
    from execution.reminder_service import InMemoryReminderService
    from runtime_core.slow_runtime import SlowRuntime

    store = InMemoryRuntimeStore()
    _seed_conversation(store)
    runtime = SlowRuntime(store=store, reminder_service=InMemoryReminderService())

    result = await runtime.run_reminder_task(
        task_id="task-1",
        dialog_id="dialog-1",
        raw_user_input="Remind me tomorrow at 9am to pay rent",
        source_session_id="s1",
    )

    task = store.get_task("task-1")
    events = store.list_task_events("task-1")

    assert result.task_id == "task-1"
    assert result.status == "completed"
    assert task is not None
    assert task["status"] == "completed"
    assert task["summary"] == "Reminder created"
    assert [event["event_kind"] for event in events] == ["accepted", "running", "completed"]


@pytest.mark.asyncio
async def test_slow_runtime_enters_waiting_user_when_time_missing() -> None:
    from execution.reminder_service import InMemoryReminderService
    from runtime_core.slow_runtime import SlowRuntime

    store = InMemoryRuntimeStore()
    _seed_conversation(store)
    runtime = SlowRuntime(store=store, reminder_service=InMemoryReminderService())

    result = await runtime.run_reminder_task(
        task_id="task-1",
        dialog_id="dialog-1",
        raw_user_input="Remind me to pay rent",
        source_session_id="s1",
    )

    task = store.get_task("task-1")
    checkpoint = store.get_checkpoint("task-1")
    events = store.list_task_events("task-1")

    assert result.status == "waiting_user"
    assert task is not None
    assert task["status"] == "waiting_user"
    assert checkpoint is not None
    assert checkpoint["payload"]["missing_field"] == "scheduled_at"
    assert [event["event_kind"] for event in events] == ["accepted", "running", "waiting_user"]


@pytest.mark.asyncio
async def test_slow_runtime_resumes_waiting_reminder_when_time_is_provided() -> None:
    from execution.reminder_service import InMemoryReminderService
    from runtime_core.slow_runtime import SlowRuntime

    store = InMemoryRuntimeStore()
    _seed_conversation(store)
    runtime = SlowRuntime(store=store, reminder_service=InMemoryReminderService())

    waiting_result = await runtime.run_reminder_task(
        task_id="task-1",
        dialog_id="dialog-1",
        raw_user_input="Remind me to pay rent",
        source_session_id="s1",
    )
    resumed_result = await runtime.resume_reminder_task(
        task_id="task-1",
        dialog_id="dialog-1",
        text="tomorrow at 9am",
        source_session_id="s1",
    )

    task = store.get_task("task-1")
    checkpoint = store.get_checkpoint("task-1")
    events = store.list_task_events("task-1")

    assert waiting_result.status == "waiting_user"
    assert resumed_result.status == "completed"
    assert resumed_result.reply_text == "Okay, I’ll remind you tomorrow at 9am."
    assert task is not None
    assert task["status"] == "completed"
    assert checkpoint is not None
    assert checkpoint["state"] == "completed"
    assert checkpoint["payload"]["scheduled_at_text"] == "tomorrow at 9am"
    assert [event["event_kind"] for event in events] == [
        "accepted",
        "running",
        "waiting_user",
        "running",
        "completed",
    ]
