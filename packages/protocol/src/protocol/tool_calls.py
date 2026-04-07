from typing import Any, Literal

from pydantic import BaseModel, ConfigDict


ToolCallState = Literal[
    "queued",
    "running",
    "waiting_approval",
    "paused",
    "completed",
    "failed",
    "cancelled",
]


class ToolCallPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    callId: str
    taskId: str
    toolName: str
    params: dict[str, Any]


class ToolProgressPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    callId: str
    state: ToolCallState
    status: str


class ToolResultPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    callId: str
    result: Any


class ToolErrorPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    callId: str
    error: str
