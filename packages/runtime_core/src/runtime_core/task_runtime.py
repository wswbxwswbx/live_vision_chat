from __future__ import annotations

from typing import Any

from runtime_store import ReminderCheckpointPayload, ReminderTaskPayload, RuntimeStore


class TaskRuntime:
    def __init__(self, *, store: RuntimeStore) -> None:
        self._store = store

    async def accept(
        self,
        *,
        task_id: str,
        dialog_id: str,
        take_attention: bool = True,
        payload: ReminderTaskPayload | None = None,
        summary: str | None = None,
    ) -> None:
        self._validate_task_dialog(task_id=task_id, dialog_id=dialog_id)
        conversation = self._require_conversation(dialog_id)
        background_task_ids = list(conversation["background_task_ids"])
        if task_id not in background_task_ids:
            background_task_ids.append(task_id)

        task_data: dict[str, object] = {
            "dialog_id": dialog_id,
            "status": "accepted",
        }
        if summary is not None:
            task_data["summary"] = summary
        if payload is not None:
            task_data["payload"] = payload

        self._store.upsert_task(
            task_id,
            task_data,
        )
        self._store.append_task_event(
            task_id,
            {
                "dialog_id": dialog_id,
                "event_kind": "accepted",
                "summary": summary or "task accepted",
            },
        )
        self._store.upsert_conversation(
            dialog_id,
            {
                "attention_owner": "slow" if take_attention else conversation["attention_owner"],
                "background_task_ids": background_task_ids,
            },
            actor="slow",
        )

    async def complete(
        self,
        *,
        task_id: str,
        dialog_id: str,
        release_attention: bool = True,
        summary: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> None:
        self._validate_task_dialog(task_id=task_id, dialog_id=dialog_id)
        conversation = self._require_conversation(dialog_id)
        background_task_ids = [
            background_task_id
            for background_task_id in conversation["background_task_ids"]
            if background_task_id != task_id
        ]
        attention_owner = conversation["attention_owner"]
        if release_attention:
            attention_owner = "slow" if background_task_ids else "fast"

        task_data: dict[str, object] = {
            "dialog_id": dialog_id,
            "status": "completed",
        }
        if summary is not None:
            task_data["summary"] = summary
        if payload is not None:
            task_data["payload"] = payload

        self._store.upsert_task(
            task_id,
            task_data,
        )
        self._store.append_task_event(
            task_id,
            {
                "dialog_id": dialog_id,
                "event_kind": "completed",
                "summary": summary or "task completed",
                "payload": payload,
            },
        )
        self._store.upsert_conversation(
            dialog_id,
            {
                "attention_owner": attention_owner,
                "background_task_ids": background_task_ids,
            },
            actor="slow",
        )

    async def mark_running(
        self,
        *,
        task_id: str,
        dialog_id: str,
        summary: str | None = None,
    ) -> None:
        self._validate_task_dialog(task_id=task_id, dialog_id=dialog_id)
        self._store.upsert_task(
            task_id,
            {
                "dialog_id": dialog_id,
                "status": "running",
                "summary": summary,
            },
        )
        self._store.append_task_event(
            task_id,
            {
                "dialog_id": dialog_id,
                "event_kind": "running",
                "summary": summary or "task running",
            },
        )

    async def mark_waiting_user(
        self,
        *,
        task_id: str,
        dialog_id: str,
        summary: str,
        checkpoint_payload: ReminderCheckpointPayload,
    ) -> None:
        self._validate_task_dialog(task_id=task_id, dialog_id=dialog_id)
        self._store.upsert_task(
            task_id,
            {
                "dialog_id": dialog_id,
                "status": "waiting_user",
                "summary": summary,
            },
        )
        self._store.upsert_checkpoint(
            task_id,
            {
                "dialog_id": dialog_id,
                "state": "waiting_user",
                "payload": checkpoint_payload,
            },
        )
        self._store.append_task_event(
            task_id,
            {
                "dialog_id": dialog_id,
                "event_kind": "waiting_user",
                "summary": summary,
                "payload": checkpoint_payload,
            },
        )

    async def mark_failed(
        self,
        *,
        task_id: str,
        dialog_id: str,
        summary: str,
    ) -> None:
        self._validate_task_dialog(task_id=task_id, dialog_id=dialog_id)
        conversation = self._require_conversation(dialog_id)
        background_task_ids = [
            background_task_id
            for background_task_id in conversation["background_task_ids"]
            if background_task_id != task_id
        ]
        attention_owner = "slow" if background_task_ids else "fast"

        self._store.upsert_task(
            task_id,
            {
                "dialog_id": dialog_id,
                "status": "failed",
                "summary": summary,
            },
        )
        self._store.append_task_event(
            task_id,
            {
                "dialog_id": dialog_id,
                "event_kind": "failed",
                "summary": summary,
            },
        )
        self._store.upsert_conversation(
            dialog_id,
            {
                "attention_owner": attention_owner,
                "background_task_ids": background_task_ids,
            },
            actor="slow",
        )

    def _require_conversation(self, dialog_id: str) -> dict[str, object]:
        conversation = self._store.get_conversation(dialog_id)
        if conversation is None:
            raise ValueError(f"conversation does not exist: {dialog_id}")
        return conversation

    def _validate_task_dialog(self, *, task_id: str, dialog_id: str) -> None:
        task = self._store.get_task(task_id)
        if task is None:
            return

        existing_dialog_id = task.get("dialog_id")
        if existing_dialog_id is not None and existing_dialog_id != dialog_id:
            raise ValueError(
                f"task {task_id} belongs to dialog {existing_dialog_id}, not {dialog_id}",
            )
