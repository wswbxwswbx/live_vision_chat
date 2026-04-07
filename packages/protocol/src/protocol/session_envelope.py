from pydantic import BaseModel, ConfigDict


class SessionEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sessionId: str
    messageId: str
