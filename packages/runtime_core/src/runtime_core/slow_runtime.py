from __future__ import annotations

from dataclasses import dataclass

from runtime_store import RuntimeStore

from .task_runtime import TaskRuntime


@dataclass(frozen=True)
class SlowRunResult:
    task_id: str
    status: str


class SlowRuntime:
    def __init__(self, *, store: RuntimeStore) -> None:
        self._task_runtime = TaskRuntime(store=store)

    async def run_once(self, *, task_id: str, dialog_id: str) -> SlowRunResult:
        await self._task_runtime.accept(task_id=task_id, dialog_id=dialog_id)
        await self._task_runtime.complete(task_id=task_id, dialog_id=dialog_id)
        return SlowRunResult(task_id=task_id, status="completed")
