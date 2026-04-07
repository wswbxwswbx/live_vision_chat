from __future__ import annotations

from dataclasses import dataclass

from runtime_store import (
    CheckpointRecord,
    ConversationState,
    RuntimeStore,
    TaskEventRecord,
    TaskRecord,
    ToolCallRecord,
)

from .session_conversation_registry import SessionConversationRegistry
from .session_task_registry import SessionTaskRegistry


@dataclass(frozen=True)
class SessionTaskSnapshot:
    task: TaskRecord | None
    checkpoint: CheckpointRecord | None
    events: list[TaskEventRecord]
    tool_calls: list[ToolCallRecord]


@dataclass(frozen=True)
class SessionSnapshot:
    session_id: str
    dialog_id: str
    conversation: ConversationState
    tasks: list[SessionTaskSnapshot]


class SessionSnapshotReader:
    def __init__(
        self,
        *,
        store: RuntimeStore,
        conversation_registry: SessionConversationRegistry,
        task_registry: SessionTaskRegistry,
    ) -> None:
        self._store = store
        self._conversation_registry = conversation_registry
        self._task_registry = task_registry

    def get_session_snapshot(self, session_id: str) -> SessionSnapshot | None:
        dialog_id = self._conversation_registry.get_dialog_id(session_id)
        if dialog_id is None:
            return None

        conversation = self._store.get_conversation(dialog_id)
        if conversation is None:
            return None

        conversation_task_ids = [
            *(
                [conversation["foreground_task_id"]]
                if conversation["foreground_task_id"] is not None
                else []
            ),
            *conversation["background_task_ids"],
        ]
        task_ids = list(
            dict.fromkeys(
                [*self._task_registry.list_task_ids(session_id), *conversation_task_ids]
            )
        )

        return SessionSnapshot(
            session_id=session_id,
            dialog_id=dialog_id,
            conversation=conversation,
            tasks=self._build_task_snapshots(task_ids),
        )

    def _build_task_snapshots(self, task_ids: list[str]) -> list[SessionTaskSnapshot]:
        snapshots: list[SessionTaskSnapshot] = []
        for task_id in task_ids:
            task = self._store.get_task(task_id)
            if task is None:
                continue

            snapshots.append(
                SessionTaskSnapshot(
                    task=task,
                    checkpoint=self._store.get_checkpoint(task_id),
                    events=self._store.list_task_events(task_id),
                    tool_calls=self._store.list_tool_calls(task_id),
                )
            )

        return snapshots
