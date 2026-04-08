from __future__ import annotations

from datetime import UTC, datetime
from typing import Protocol, TypedDict


class ReminderRecord(TypedDict):
    id: str
    title: str
    scheduled_at_text: str
    scheduled_at_iso: str | None
    status: str
    source_session_id: str
    task_id: str
    raw_user_input: str
    created_at: str


class ReminderService(Protocol):
    def create_reminder(
        self,
        *,
        title: str,
        scheduled_at_text: str,
        scheduled_at_iso: str | None,
        source_session_id: str,
        task_id: str,
        raw_user_input: str,
    ) -> ReminderRecord: ...

    def list_reminders(self) -> list[ReminderRecord]: ...


class InMemoryReminderService:
    def __init__(self) -> None:
        self._reminders: list[ReminderRecord] = []
        self._next_id = 1

    def create_reminder(
        self,
        *,
        title: str,
        scheduled_at_text: str,
        scheduled_at_iso: str | None,
        source_session_id: str,
        task_id: str,
        raw_user_input: str,
    ) -> ReminderRecord:
        reminder: ReminderRecord = {
            "id": f"reminder-{self._next_id}",
            "title": title,
            "scheduled_at_text": scheduled_at_text,
            "scheduled_at_iso": scheduled_at_iso,
            "status": "scheduled",
            "source_session_id": source_session_id,
            "task_id": task_id,
            "raw_user_input": raw_user_input,
            "created_at": datetime.now(UTC).isoformat(),
        }
        self._next_id += 1
        self._reminders.append(reminder)
        return reminder

    def list_reminders(self) -> list[ReminderRecord]:
        return [dict(reminder) for reminder in self._reminders]
