from __future__ import annotations

from protocol.messages import ClientMessage
from runtime_store import InMemoryRuntimeStore, RuntimeStore

from .fast_runtime import FastRuntime, FastTurnResult
from .session_conversation_registry import SessionConversationRegistry
from .session_snapshot import SessionSnapshot, SessionSnapshotReader
from .session_task_registry import SessionTaskRegistry
from .slow_runtime import SlowRuntime


class RuntimeFacade:
    def __init__(
        self,
        *,
        store: RuntimeStore | None = None,
        conversation_registry: SessionConversationRegistry | None = None,
        task_registry: SessionTaskRegistry | None = None,
        fast_runtime: FastRuntime | None = None,
        slow_runtime: SlowRuntime | None = None,
        snapshot_reader: SessionSnapshotReader | None = None,
    ) -> None:
        resolved_store = store or InMemoryRuntimeStore()
        resolved_conversation_registry = (
            conversation_registry or SessionConversationRegistry()
        )
        resolved_task_registry = task_registry or SessionTaskRegistry()

        self._store = resolved_store
        self._conversation_registry = resolved_conversation_registry
        self._task_registry = resolved_task_registry
        self._fast_runtime = fast_runtime or FastRuntime(
            store=resolved_store,
            conversation_registry=resolved_conversation_registry,
            task_registry=resolved_task_registry,
        )
        self._slow_runtime = slow_runtime or SlowRuntime(store=resolved_store)
        self._snapshot_reader = snapshot_reader or SessionSnapshotReader(
            store=resolved_store,
            conversation_registry=resolved_conversation_registry,
            task_registry=resolved_task_registry,
        )

    async def handle_client_message(self, message: ClientMessage) -> FastTurnResult:
        if message.type == "turn":
            result = await self._fast_runtime.handle_turn(
                session_id=message.sessionId,
                text=message.payload.text,
            )
            if result.handoff_task_id is not None:
                task = self._store.get_task(result.handoff_task_id)
                dialog_id = self._conversation_registry.get_dialog_id(message.sessionId)
                if task is not None and dialog_id is not None:
                    payload = task.get("payload")
                    raw_user_input = payload.get("raw_user_input") if isinstance(payload, dict) else None
                    if isinstance(raw_user_input, str):
                        slow_result = await self._slow_runtime.run_reminder_task(
                            task_id=result.handoff_task_id,
                            dialog_id=dialog_id,
                            raw_user_input=raw_user_input,
                            source_session_id=message.sessionId,
                        )
                        if slow_result.reply_text is not None:
                            return FastTurnResult(
                                reply_text=slow_result.reply_text,
                                handoff_task_id=(
                                    result.handoff_task_id
                                    if slow_result.status == "waiting_user"
                                    else None
                                ),
                            )
            return result

        if message.type == "handoff_resume":
            task_id = message.payload.taskId
            session_id = self._task_registry.get_session_id(task_id)
            if session_id != message.sessionId:
                raise ValueError(
                    f"task {task_id} does not belong to session {message.sessionId}"
                )

            task = self._store.get_task(task_id)
            if task is None:
                raise ValueError(f"task does not exist: {task_id}")

            dialog_id = task.get("dialog_id")
            if not isinstance(dialog_id, str):
                raise ValueError(f"task {task_id} is missing dialog_id")

            result = await self._slow_runtime.resume_reminder_task(
                task_id=task_id,
                dialog_id=dialog_id,
                text=message.payload.text,
                source_session_id=message.sessionId,
            )
            return FastTurnResult(reply_text=result.reply_text)

        raise NotImplementedError(f"unsupported client message type: {message.type}")

    def get_session_snapshot(self, session_id: str) -> SessionSnapshot | None:
        return self._snapshot_reader.get_session_snapshot(session_id)
