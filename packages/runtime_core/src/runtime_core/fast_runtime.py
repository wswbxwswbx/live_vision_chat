from __future__ import annotations

from dataclasses import dataclass

from runtime_store import RuntimeStore

from .session_conversation_registry import SessionConversationRegistry


@dataclass(frozen=True)
class FastTurnResult:
    reply_text: str | None


class FastRuntime:
    def __init__(
        self,
        *,
        store: RuntimeStore,
        conversation_registry: SessionConversationRegistry,
    ) -> None:
        self._store = store
        self._conversation_registry = conversation_registry

    async def handle_turn(self, session_id: str, text: str) -> FastTurnResult:
        del text
        self._ensure_conversation(session_id)
        return FastTurnResult(reply_text="stub")

    def _ensure_conversation(self, session_id: str) -> None:
        dialog_id = self._conversation_registry.get_dialog_id(session_id)
        if dialog_id is None:
            dialog_id = session_id
            self._conversation_registry.bind_dialog(session_id, dialog_id)

        if self._store.get_conversation(dialog_id) is not None:
            return

        self._store.upsert_conversation(
            dialog_id,
            {
                "dialog_id": dialog_id,
                "speaker_owner": "fast",
                "attention_owner": "fast",
                "foreground_task_id": None,
                "background_task_ids": [],
                "interrupt_epoch": 0,
            },
            actor="system",
        )
