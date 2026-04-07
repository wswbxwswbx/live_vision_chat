import pytest

from protocol.messages import parse_client_message, parse_server_message


def test_parse_turn_message() -> None:
    payload = {"type": "turn", "sessionId": "s1", "messageId": "m1", "payload": {"text": "hi"}}
    message = parse_client_message(payload)
    assert message.type == "turn"
    assert message.payload.text == "hi"


def test_parse_audio_chunk_message() -> None:
    payload = {
        "type": "audio_chunk",
        "sessionId": "s1",
        "messageId": "m-a1",
        "payload": {
            "mimeType": "audio/webm;codecs=opus",
            "data": "Zm9v",
            "sequence": 1,
            "timestampMs": 1000,
            "durationMs": 100,
        },
    }

    message = parse_client_message(payload)
    assert message.type == "audio_chunk"
    assert message.payload.sequence == 1
    assert message.payload.durationMs == 100


def test_parse_video_frame_message() -> None:
    payload = {
        "type": "video_frame",
        "sessionId": "s1",
        "messageId": "m-v1",
        "payload": {
            "mimeType": "image/jpeg",
            "data": "YmFy",
            "sequence": 3,
            "timestampMs": 2000,
            "width": 640,
            "height": 360,
        },
    }

    message = parse_client_message(payload)
    assert message.type == "video_frame"
    assert message.payload.sequence == 3
    assert message.payload.width == 640


def test_parse_client_message_rejects_invalid_type() -> None:
    payload = {"type": "nope", "sessionId": "s1", "messageId": "m1", "payload": {"text": "hi"}}

    with pytest.raises(Exception, match="type"):
        parse_client_message(payload)


def test_parse_client_message_rejects_missing_required_field() -> None:
    payload = {"type": "turn", "sessionId": "s1", "payload": {"text": "hi"}}

    with pytest.raises(Exception, match="messageId"):
        parse_client_message(payload)


def test_parse_server_message_succeeds_for_tool_call() -> None:
    payload = {
        "type": "tool_call",
        "sessionId": "s1",
        "messageId": "m2",
        "payload": {
            "callId": "c1",
            "taskId": "t1",
            "toolName": "camera_capture",
            "params": {},
        },
    }

    message = parse_server_message(payload)
    assert message.type == "tool_call"
    assert message.payload.toolName == "camera_capture"


def test_parse_server_message_succeeds_for_assistant_text() -> None:
    payload = {
        "type": "assistant_text",
        "sessionId": "s1",
        "messageId": "m3",
        "payload": {
            "text": "hello there",
            "source": "fast",
        },
    }

    message = parse_server_message(payload)
    assert message.type == "assistant_text"
    assert message.payload.text == "hello there"


def test_parse_client_message_rejects_unknown_field() -> None:
    payload = {
        "type": "turn",
        "sessionId": "s1",
        "messageId": "m1",
        "unexpected": "value",
        "payload": {"text": "hi"},
    }

    with pytest.raises(Exception, match="unexpected"):
        parse_client_message(payload)


def test_parse_client_message_rejects_unknown_nested_payload_field() -> None:
    payload = {
        "type": "turn",
        "sessionId": "s1",
        "messageId": "m1",
        "payload": {"text": "hi", "unexpected": "value"},
    }

    with pytest.raises(Exception, match="unexpected"):
        parse_client_message(payload)


def test_parse_server_message_rejects_unknown_nested_payload_field() -> None:
    payload = {
        "type": "tool_call",
        "sessionId": "s1",
        "messageId": "m2",
        "payload": {
            "callId": "c1",
            "taskId": "t1",
            "toolName": "camera_capture",
            "params": {},
            "unexpected": "value",
        },
    }

    with pytest.raises(Exception, match="unexpected"):
        parse_server_message(payload)


def test_parse_server_message_rejects_unknown_top_level_field() -> None:
    payload = {
        "type": "tool_call",
        "sessionId": "s1",
        "messageId": "m2",
        "unexpected": "value",
        "payload": {
            "callId": "c1",
            "taskId": "t1",
            "toolName": "camera_capture",
            "params": {},
        },
    }

    with pytest.raises(Exception, match="unexpected"):
        parse_server_message(payload)
