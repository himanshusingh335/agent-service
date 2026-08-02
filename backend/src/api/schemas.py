from typing import Literal

from pydantic import BaseModel


class ChatRequest(BaseModel):
    session_id: str
    message: str


class ChatResponse(BaseModel):
    session_id: str
    reply: str


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
