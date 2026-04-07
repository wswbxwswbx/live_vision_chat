from __future__ import annotations

from runtime_store import RuntimeStore


class TaskRuntime:
    def __init__(self, *, store: RuntimeStore) -> None:
        self._store = store

    async def accept(
        self,
        *,
        task_id: str,
        dialog_id: str,
        take_attention: bool = True,
    ) -> None:
        self._validate_task_dialog(task_id=task_id, dialog_id=dialog_id)
        conversation = self._require_conversation(dialog_id)
        background_task_ids = list(conversation["background_task_ids"])
        if task_id not in background_task_ids:
            background_task_ids.append(task_id)

        self._store.upsert_task(
            task_id,
            {
                "dialog_id": dialog_id,
                "status": "accepted",
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

        self._store.upsert_task(
            task_id,
            {
                "dialog_id": dialog_id,
                "status": "completed",
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
