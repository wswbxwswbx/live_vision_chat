import pytest


@pytest.mark.asyncio
async def test_slow_task_runner_completes_without_queueing() -> None:
    from execution.slow_task_runner import SlowTaskRunner

    runner = SlowTaskRunner()

    result = await runner.run_once(task_id="task-1", dialog_id="dialog-1")

    assert result.task_id == "task-1"
    assert result.dialog_id == "dialog-1"
    assert result.states == ["running", "completed"]
    assert result.status == "completed"
