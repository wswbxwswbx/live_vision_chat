from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class SlowTaskRunResult:
    task_id: str
    dialog_id: str
    states: list[str] = field(default_factory=lambda: ["running", "completed"])
    status: str = "completed"


class SlowTaskRunner:
    async def run_once(self, *, task_id: str, dialog_id: str) -> SlowTaskRunResult:
        return SlowTaskRunResult(task_id=task_id, dialog_id=dialog_id)
