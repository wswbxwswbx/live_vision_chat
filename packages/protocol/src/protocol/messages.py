from typing import Annotated, Literal, TypeAlias, Union

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

from .session_envelope import SessionEnvelope
from .task_events import TaskEventPayload
from .tool_calls import (
    ToolCallPayload,
    ToolErrorPayload,
    ToolProgressPayload,
    ToolResultPayload,
)


class TurnPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str


class HandoffResumePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    taskId: str
    text: str


class AudioChunkPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mimeType: str
    data: str
    sequence: int
    timestampMs: int
    durationMs: int
    taskId: str | None = None


class VideoFramePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mimeType: str
    data: str
    sequence: int
    timestampMs: int
    width: int
    height: int
    taskId: str | None = None


class AssistantTextPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str
    source: Literal["fast", "slow", "system"]


class TurnMessage(SessionEnvelope):
    model_config = ConfigDict(extra="forbid")

    type: Literal["turn"]
    payload: TurnPayload


class HandoffResumeMessage(SessionEnvelope):
    model_config = ConfigDict(extra="forbid")

    type: Literal["handoff_resume"]
    payload: HandoffResumePayload


class AudioChunkMessage(SessionEnvelope):
    model_config = ConfigDict(extra="forbid")

    type: Literal["audio_chunk"]
    payload: AudioChunkPayload


class VideoFrameMessage(SessionEnvelope):
    model_config = ConfigDict(extra="forbid")

    type: Literal["video_frame"]
    payload: VideoFramePayload


class ToolResultMessage(SessionEnvelope):
    model_config = ConfigDict(extra="forbid")

    type: Literal["tool_result"]
    payload: ToolResultPayload


class ToolErrorMessage(SessionEnvelope):
    model_config = ConfigDict(extra="forbid")

    type: Literal["tool_error"]
    payload: ToolErrorPayload


class TaskEventMessage(SessionEnvelope):
    model_config = ConfigDict(extra="forbid")

    type: Literal["task_event"]
    payload: TaskEventPayload


class ToolCallMessage(SessionEnvelope):
    model_config = ConfigDict(extra="forbid")

    type: Literal["tool_call"]
    payload: ToolCallPayload


class ToolProgressMessage(SessionEnvelope):
    model_config = ConfigDict(extra="forbid")

    type: Literal["tool_progress"]
    payload: ToolProgressPayload


class AssistantTextMessage(SessionEnvelope):
    model_config = ConfigDict(extra="forbid")

    type: Literal["assistant_text"]
    payload: AssistantTextPayload


ClientMessage: TypeAlias = Annotated[
    Union[
        TurnMessage,
        HandoffResumeMessage,
        AudioChunkMessage,
        VideoFrameMessage,
        ToolResultMessage,
        ToolErrorMessage,
    ],
    Field(discriminator="type"),
]

ServerMessage: TypeAlias = Annotated[
    Union[
        TaskEventMessage,
        ToolCallMessage,
        ToolProgressMessage,
        ToolResultMessage,
        ToolErrorMessage,
        AssistantTextMessage,
    ],
    Field(discriminator="type"),
]

_client_message_adapter = TypeAdapter(ClientMessage)
_server_message_adapter = TypeAdapter(ServerMessage)


def parse_client_message(input: object) -> ClientMessage:
    return _client_message_adapter.validate_python(input)


def parse_server_message(input: object) -> ServerMessage:
    return _server_message_adapter.validate_python(input)
