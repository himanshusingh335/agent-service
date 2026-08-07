from typing import Literal

from pydantic import BaseModel, ConfigDict


class ChatRequest(BaseModel):
    session_id: str
    message: str


class PendingAction(BaseModel):
    name: str
    args: dict
    description: str | None = None


class ChatResponse(BaseModel):
    session_id: str
    reply: str | None = None
    pending_actions: list[PendingAction] | None = None


class Decision(BaseModel):
    type: Literal["approve", "reject"]
    message: str | None = None
    """Explanation shown to the model when `type` is `reject`."""


class ResumeRequest(BaseModel):
    session_id: str
    decisions: list[Decision]


class ToolCallInfo(BaseModel):
    id: str
    name: str
    args: dict


class HistoryMessage(BaseModel):
    role: Literal["user", "ai", "tool"]
    content: str
    tool_calls: list[ToolCallInfo] | None = None
    tool_call_id: str | None = None
    tool_name: str | None = None


class ChatHistoryResponse(BaseModel):
    session_id: str
    messages: list[HistoryMessage]


class LogEntry(BaseModel):
    model_config = ConfigDict(extra="allow")

    timestamp: str
    level: str
    logger: str
    session_id: str
    message: str


class SessionLogsResponse(BaseModel):
    session_id: str
    logs: list[LogEntry]
    total: int
    limit: int
    offset: int
