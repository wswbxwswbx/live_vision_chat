from typing import Any, Literal, TypedDict


SpeakerOwner = Literal["user", "fast", "slow"]
AttentionOwner = Literal["fast", "slow"]


class ConversationState(TypedDict):
    dialog_id: str
    speaker_owner: SpeakerOwner
    attention_owner: AttentionOwner
    foreground_task_id: str | None
    background_task_ids: list[str]
    interrupt_epoch: int


class TaskRecord(TypedDict, total=False):
    task_id: str
    dialog_id: str
    status: str
    summary: str
    payload: dict[str, Any]


class CheckpointRecord(TypedDict, total=False):
    task_id: str
    dialog_id: str
    state: str
    payload: dict[str, Any]


class TaskEventRecord(TypedDict, total=False):
    task_id: str
    dialog_id: str
    event_kind: str
    summary: str
    payload: dict[str, Any]


class ToolCallRecord(TypedDict, total=False):
    call_id: str
    task_id: str
    status: str
    tool_name: str
    payload: dict[str, Any]
