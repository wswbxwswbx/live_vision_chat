import pytest

from protocol.messages import parse_client_message


@pytest.mark.asyncio
async def test_runtime_facade_routes_turn_and_exposes_snapshot() -> None:
    from runtime_core.runtime_facade import RuntimeFacade

    facade = RuntimeFacade()
    turn_message = parse_client_message(
        {
            "type": "turn",
            "sessionId": "s1",
            "messageId": "m1",
            "payload": {"text": "hello"},
        }
    )

    result = await facade.handle_client_message(turn_message)
    snapshot = facade.get_session_snapshot("s1")

    assert result.reply_text == "Fast reply: hello"
    assert result.handoff_task_id is None
    assert snapshot is not None
    assert snapshot.session_id == "s1"
    assert snapshot.dialog_id == "s1"
    assert snapshot.conversation == {
        "dialog_id": "s1",
        "speaker_owner": "fast",
        "attention_owner": "fast",
        "foreground_task_id": None,
        "background_task_ids": [],
        "interrupt_epoch": 0,
    }
    assert snapshot.tasks == []


def test_runtime_facade_returns_none_for_unknown_session_snapshot() -> None:
    from runtime_core.runtime_facade import RuntimeFacade

    facade = RuntimeFacade()

    assert facade.get_session_snapshot("missing") is None


@pytest.mark.asyncio
async def test_runtime_facade_routes_handoff_resume_to_waiting_reminder_task() -> None:
    from runtime_core.runtime_facade import RuntimeFacade

    facade = RuntimeFacade()
    initial_turn = parse_client_message(
        {
            "type": "turn",
            "sessionId": "s1",
            "messageId": "m1",
            "payload": {"text": "Remind me to pay rent"},
        }
    )
    resume_message = parse_client_message(
        {
            "type": "handoff_resume",
            "sessionId": "s1",
            "messageId": "m2",
            "payload": {
                "taskId": "task-1",
                "text": "tomorrow at 9am",
            },
        }
    )

    first_result = await facade.handle_client_message(initial_turn)
    resume_result = await facade.handle_client_message(resume_message)
    snapshot = facade.get_session_snapshot("s1")

    assert first_result.reply_text == "When should I remind you?"
    assert first_result.handoff_task_id == "task-1"
    assert resume_result.reply_text == "Okay, I’ll remind you tomorrow at 9am."
    assert resume_result.handoff_task_id is None
    assert snapshot is not None
    assert snapshot.tasks[0].task is not None
    assert snapshot.tasks[0].task["status"] == "completed"


@pytest.mark.asyncio
async def test_runtime_facade_clears_handoff_task_id_when_reminder_completes_immediately() -> None:
    from runtime_core.runtime_facade import RuntimeFacade

    facade = RuntimeFacade()
    turn_message = parse_client_message(
        {
            "type": "turn",
            "sessionId": "s1",
            "messageId": "m1",
            "payload": {"text": "Remind me tomorrow at 9am to pay rent"},
        }
    )

    result = await facade.handle_client_message(turn_message)
    snapshot = facade.get_session_snapshot("s1")

    assert result.reply_text == "Okay, I’ll remind you tomorrow at 9am."
    assert result.handoff_task_id is None
    assert snapshot is not None
    assert snapshot.tasks[0].task is not None
    assert snapshot.tasks[0].task["status"] == "completed"


@pytest.mark.asyncio
async def test_runtime_facade_rejects_handoff_resume_from_another_session() -> None:
    from runtime_core.runtime_facade import RuntimeFacade

    facade = RuntimeFacade()
    initial_turn = parse_client_message(
        {
            "type": "turn",
            "sessionId": "s1",
            "messageId": "m1",
            "payload": {"text": "Remind me to pay rent"},
        }
    )
    resume_message = parse_client_message(
        {
            "type": "handoff_resume",
            "sessionId": "s2",
            "messageId": "m2",
            "payload": {
                "taskId": "task-1",
                "text": "tomorrow at 9am",
            },
        }
    )

    await facade.handle_client_message(initial_turn)

    with pytest.raises(ValueError, match="does not belong to session"):
        await facade.handle_client_message(resume_message)
