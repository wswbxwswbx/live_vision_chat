from __future__ import annotations

from copy import deepcopy
from typing import cast

from .interfaces import RuntimeStore
from .models import (
    CheckpointRecord,
    ConversationState,
    TaskEventRecord,
    TaskRecord,
    ToolCallRecord,
)


class InMemoryRuntimeStore(RuntimeStore):
    def __init__(self) -> None:
        self._conversations: dict[str, ConversationState] = {}
        self._tasks: dict[str, TaskRecord] = {}
        self._checkpoints: dict[str, CheckpointRecord] = {}
        self._events: dict[str, list[TaskEventRecord]] = {}
        self._tool_calls: dict[str, ToolCallRecord] = {}

    def upsert_conversation(
        self,
        dialog_id: str,
        data: ConversationState | dict[str, object],
        *,
        actor: str,
    ) -> ConversationState:
        existing = self._conversations.get(dialog_id)
        merged = dict(existing) if existing is not None else {}
        merged.update(data)
        merged["dialog_id"] = dialog_id

        conversation = cast(ConversationState, merged)
        self._validate_conversation(existing, conversation, actor=actor)

        stored = self._copy_conversation(conversation)
        self._conversations[dialog_id] = stored
        return self._copy_conversation(stored)

    def get_conversation(self, dialog_id: str) -> ConversationState | None:
        conversation = self._conversations.get(dialog_id)
        if conversation is None:
            return None
        return self._copy_conversation(conversation)

    def upsert_task(self, task_id: str, data: TaskRecord | dict[str, object]) -> TaskRecord:
        merged = dict(self._tasks.get(task_id, {}))
        merged.update(data)
        merged["task_id"] = task_id

        record = cast(TaskRecord, merged)
        stored = self._copy_record(record)
        self._tasks[task_id] = stored
        return self._copy_record(stored)

    def get_task(self, task_id: str) -> TaskRecord | None:
        record = self._tasks.get(task_id)
        if record is None:
            return None
        return self._copy_record(record)

    def upsert_checkpoint(
        self,
        task_id: str,
        data: CheckpointRecord | dict[str, object],
    ) -> CheckpointRecord:
        merged = dict(self._checkpoints.get(task_id, {}))
        merged.update(data)
        merged["task_id"] = task_id

        record = cast(CheckpointRecord, merged)
        stored = self._copy_record(record)
        self._checkpoints[task_id] = stored
        return self._copy_record(stored)

    def get_checkpoint(self, task_id: str) -> CheckpointRecord | None:
        record = self._checkpoints.get(task_id)
        if record is None:
            return None
        return self._copy_record(record)

    def append_task_event(
        self,
        task_id: str,
        data: TaskEventRecord | dict[str, object],
    ) -> TaskEventRecord:
        record = dict(data)
        record["task_id"] = task_id

        stored = cast(TaskEventRecord, self._copy_record(cast(TaskEventRecord, record)))
        self._events.setdefault(task_id, []).append(stored)
        return self._copy_record(stored)

    def list_task_events(self, task_id: str) -> list[TaskEventRecord]:
        return [self._copy_record(record) for record in self._events.get(task_id, [])]

    def upsert_tool_call(
        self,
        call_id: str,
        data: ToolCallRecord | dict[str, object],
    ) -> ToolCallRecord:
        merged = dict(self._tool_calls.get(call_id, {}))
        merged.update(data)
        merged["call_id"] = call_id

        record = cast(ToolCallRecord, merged)
        stored = self._copy_record(record)
        self._tool_calls[call_id] = stored
        return self._copy_record(stored)

    def get_tool_call(self, call_id: str) -> ToolCallRecord | None:
        record = self._tool_calls.get(call_id)
        if record is None:
            return None
        return self._copy_record(record)

    def list_tool_calls(self, task_id: str) -> list[ToolCallRecord]:
        return [
            self._copy_record(record)
            for record in self._tool_calls.values()
            if record.get("task_id") == task_id
        ]

    def _validate_conversation(
        self,
        existing: ConversationState | None,
        candidate: ConversationState,
        *,
        actor: str,
    ) -> None:
        required_fields = {
            "dialog_id",
            "speaker_owner",
            "attention_owner",
            "foreground_task_id",
            "background_task_ids",
            "interrupt_epoch",
        }
        missing = required_fields.difference(candidate.keys())
        if missing:
            missing_fields = ", ".join(sorted(missing))
            raise ValueError(f"conversation missing required fields: {missing_fields}")

        background_task_ids = candidate["background_task_ids"]
        if len(background_task_ids) != len(set(background_task_ids)):
            raise ValueError("background_task_ids must be unique")

        foreground_task_id = candidate["foreground_task_id"]
        if foreground_task_id is not None and foreground_task_id in background_task_ids:
            raise ValueError("foreground_task_id cannot also appear in background_task_ids")

        if existing is not None:
            if candidate["interrupt_epoch"] < existing["interrupt_epoch"]:
                raise ValueError("interrupt_epoch cannot go backwards")

            if (
                candidate["speaker_owner"] != existing["speaker_owner"]
                and actor != "system"
            ):
                raise ValueError("speaker_owner can only be changed by system")

    def _copy_conversation(self, conversation: ConversationState) -> ConversationState:
        return cast(ConversationState, deepcopy(conversation))

    def _copy_record(self, record: dict[str, object]) -> dict[str, object]:
        return cast(dict[str, object], deepcopy(record))
