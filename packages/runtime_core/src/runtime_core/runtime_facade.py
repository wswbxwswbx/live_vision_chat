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
        )
        self._slow_runtime = slow_runtime or SlowRuntime(store=resolved_store)
        self._snapshot_reader = snapshot_reader or SessionSnapshotReader(
            store=resolved_store,
            conversation_registry=resolved_conversation_registry,
            task_registry=resolved_task_registry,
        )

    async def handle_client_message(self, message: ClientMessage) -> FastTurnResult:
        if message.type == "turn":
            return await self._fast_runtime.handle_turn(
                session_id=message.sessionId,
                text=message.payload.text,
            )

        raise NotImplementedError(f"unsupported client message type: {message.type}")

    def get_session_snapshot(self, session_id: str) -> SessionSnapshot | None:
        return self._snapshot_reader.get_session_snapshot(session_id)
