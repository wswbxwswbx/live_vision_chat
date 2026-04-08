from __future__ import annotations

from dataclasses import dataclass

from runtime_store import ReminderTaskPayload, RuntimeStore

from .reminder_classifier import ReminderIntent, RuleBasedReminderClassifier
from .session_conversation_registry import SessionConversationRegistry
from .session_task_registry import SessionTaskRegistry


@dataclass(frozen=True)
class FastTurnResult:
    reply_text: str | None
    handoff_task_id: str | None = None


class FastRuntime:
    def __init__(
        self,
        *,
        store: RuntimeStore,
        conversation_registry: SessionConversationRegistry,
        task_registry: SessionTaskRegistry,
        classifier: RuleBasedReminderClassifier | None = None,
    ) -> None:
        self._store = store
        self._conversation_registry = conversation_registry
        self._task_registry = task_registry
        self._classifier = classifier or RuleBasedReminderClassifier()
        self._next_task_id = 1

    async def handle_turn(self, session_id: str, text: str) -> FastTurnResult:
        dialog_id = self._ensure_conversation(session_id)
        intent = self._classifier.classify(text)
        if intent == ReminderIntent.CREATE_REMINDER:
            task_id = self._create_reminder_task(
                session_id=session_id,
                dialog_id=dialog_id,
                raw_user_input=text,
            )
            return FastTurnResult(
                reply_text="I’ll handle that reminder in the background.",
                handoff_task_id=task_id,
            )

        return FastTurnResult(reply_text=f"Fast reply: {text}")

    def _ensure_conversation(self, session_id: str) -> str:
        dialog_id = self._conversation_registry.get_dialog_id(session_id)
        if dialog_id is None:
            dialog_id = session_id
            self._conversation_registry.bind_dialog(session_id, dialog_id)

        if self._store.get_conversation(dialog_id) is not None:
            return dialog_id

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
        return dialog_id

    def _create_reminder_task(
        self,
        *,
        session_id: str,
        dialog_id: str,
        raw_user_input: str,
    ) -> str:
        task_id = f"task-{self._next_task_id}"
        self._next_task_id += 1

        payload: ReminderTaskPayload = {
            "task_type": "create_reminder",
            "title": raw_user_input,
            "raw_user_input": raw_user_input,
            "scheduled_at_text": None,
        }
        self._store.upsert_task(
            task_id,
            {
                "dialog_id": dialog_id,
                "status": "accepted",
                "summary": "create_reminder",
                "payload": payload,
            },
        )
        self._task_registry.bind_task(session_id, task_id)
        return task_id
