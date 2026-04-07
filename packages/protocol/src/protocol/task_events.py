from typing import Literal

from pydantic import BaseModel, ConfigDict


class TaskEventPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    taskId: str
    eventKind: Literal["accepted", "progress", "need_user_input", "completed", "failed"]
    summary: str
