from typing import Protocol

from .models import (
    CheckpointRecord,
    ConversationState,
    TaskEventRecord,
    TaskRecord,
    ToolCallRecord,
)


class RuntimeStore(Protocol):
    def upsert_conversation(
        self,
        dialog_id: str,
        data: ConversationState | dict[str, object],
        *,
        actor: str,
    ) -> ConversationState: ...

    def get_conversation(self, dialog_id: str) -> ConversationState | None: ...

    def upsert_task(self, task_id: str, data: TaskRecord | dict[str, object]) -> TaskRecord: ...

    def get_task(self, task_id: str) -> TaskRecord | None: ...

    def upsert_checkpoint(
        self,
        task_id: str,
        data: CheckpointRecord | dict[str, object],
    ) -> CheckpointRecord: ...

    def get_checkpoint(self, task_id: str) -> CheckpointRecord | None: ...

    def append_task_event(
        self,
        task_id: str,
        data: TaskEventRecord | dict[str, object],
    ) -> TaskEventRecord: ...

    def list_task_events(self, task_id: str) -> list[TaskEventRecord]: ...

    def upsert_tool_call(
        self,
        call_id: str,
        data: ToolCallRecord | dict[str, object],
    ) -> ToolCallRecord: ...

    def get_tool_call(self, call_id: str) -> ToolCallRecord | None: ...

    def list_tool_calls(self, task_id: str) -> list[ToolCallRecord]: ...
