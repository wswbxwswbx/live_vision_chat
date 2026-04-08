from __future__ import annotations

from dataclasses import dataclass

from execution import InMemoryReminderService, ReminderRecord, ReminderService
from runtime_store import ReminderCheckpointPayload, ReminderTaskPayload, RuntimeStore

from .reminder_parser import parse_reminder_request
from .task_runtime import TaskRuntime


@dataclass(frozen=True)
class SlowRunResult:
    task_id: str
    status: str
    reply_text: str | None = None
    reminder: ReminderRecord | None = None


class SlowRuntime:
    def __init__(
        self,
        *,
        store: RuntimeStore,
        reminder_service: ReminderService | None = None,
    ) -> None:
        self._store = store
        self._task_runtime = TaskRuntime(store=store)
        self._reminder_service = reminder_service or InMemoryReminderService()

    async def run_once(self, *, task_id: str, dialog_id: str) -> SlowRunResult:
        await self._task_runtime.accept(task_id=task_id, dialog_id=dialog_id)
        await self._task_runtime.complete(task_id=task_id, dialog_id=dialog_id)
        return SlowRunResult(task_id=task_id, status="completed")

    async def run_reminder_task(
        self,
        *,
        task_id: str,
        dialog_id: str,
        raw_user_input: str,
        source_session_id: str,
    ) -> SlowRunResult:
        parsed = parse_reminder_request(raw_user_input)
        payload: ReminderTaskPayload = {
            "task_type": "create_reminder",
            "title": parsed.title,
            "raw_user_input": raw_user_input,
            "scheduled_at_text": parsed.scheduled_at_text,
        }

        await self._task_runtime.accept(
            task_id=task_id,
            dialog_id=dialog_id,
            payload=payload,
            summary="create_reminder",
        )
        await self._task_runtime.mark_running(
            task_id=task_id,
            dialog_id=dialog_id,
            summary="Creating reminder",
        )

        if parsed.scheduled_at_text is None:
            checkpoint_payload: ReminderCheckpointPayload = {
                "task_type": "create_reminder",
                "title": parsed.title,
                "raw_user_input": raw_user_input,
                "scheduled_at_text": None,
                "missing_field": "scheduled_at",
            }
            await self._task_runtime.mark_waiting_user(
                task_id=task_id,
                dialog_id=dialog_id,
                summary="When should I remind you?",
                checkpoint_payload=checkpoint_payload,
            )
            return SlowRunResult(
                task_id=task_id,
                status="waiting_user",
                reply_text="When should I remind you?",
            )

        reminder = self._reminder_service.create_reminder(
            title=parsed.title,
            scheduled_at_text=parsed.scheduled_at_text,
            scheduled_at_iso=None,
            source_session_id=source_session_id,
            task_id=task_id,
            raw_user_input=raw_user_input,
        )
        await self._task_runtime.complete(
            task_id=task_id,
            dialog_id=dialog_id,
            summary="Reminder created",
            payload={"reminder": reminder},
        )
        return SlowRunResult(
            task_id=task_id,
            status="completed",
            reply_text=f"Okay, I’ll remind you {parsed.scheduled_at_text}.",
            reminder=reminder,
        )
