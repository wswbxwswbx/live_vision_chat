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

    assert result.reply_text == "stub"
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
