from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping


def _read_field(data: Mapping[str, Any], *names: str) -> Any:
    for name in names:
        if name in data:
            return data[name]
    raise KeyError(names[0])


@dataclass(slots=True)
class ToolExecutionResult:
    call_id: str
    task_id: str
    tool_name: str
    states: list[str] = field(default_factory=lambda: ["running", "completed"])
    status: str = "completed"
    payload: dict[str, Any] | None = None


class ToolExecutor:
    async def execute(self, tool_call: Mapping[str, Any]) -> ToolExecutionResult:
        call_id = str(_read_field(tool_call, "call_id", "callId"))
        task_id = str(_read_field(tool_call, "task_id", "taskId"))
        tool_name = str(_read_field(tool_call, "tool_name", "toolName"))
        payload = tool_call.get("payload")
        return ToolExecutionResult(
            call_id=call_id,
            task_id=task_id,
            tool_name=tool_name,
            payload=payload if isinstance(payload, dict) else None,
        )
