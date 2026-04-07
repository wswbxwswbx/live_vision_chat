import pytest


@pytest.mark.asyncio
async def test_tool_executor_reports_progress_and_completion() -> None:
    from execution.tool_executor import ToolExecutor

    executor = ToolExecutor()

    result = await executor.execute(
        {
            "call_id": "call-1",
            "task_id": "task-1",
            "tool_name": "camera_capture",
            "payload": {"zoom": 2},
        },
    )

    assert result.call_id == "call-1"
    assert result.task_id == "task-1"
    assert result.tool_name == "camera_capture"
    assert result.states == ["running", "completed"]
    assert result.status == "completed"
