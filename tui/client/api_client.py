from collections.abc import Iterator
from typing import Any

import httpx


class AgentServiceClient:
    def __init__(self, base_url: str):
        self._base_url = base_url.rstrip("/")
        self._client = httpx.Client(base_url=self._base_url, timeout=60.0)

    def invoke(self, session_id: str, message: str) -> dict[str, Any]:
        response = self._client.post(
            "/chat/invoke", json={"session_id": session_id, "message": message}
        )
        response.raise_for_status()
        return response.json()

    def resume(self, session_id: str, decisions: list[dict[str, Any]]) -> dict[str, Any]:
        response = self._client.post(
            "/chat/resume", json={"session_id": session_id, "decisions": decisions}
        )
        response.raise_for_status()
        return response.json()

    def stream(self, session_id: str, message: str) -> Iterator[tuple[str, str]]:
        """Yield (event, data) pairs. `event` is "message" unless the server names one."""
        with self._client.stream(
            "POST",
            "/chat/stream",
            json={"session_id": session_id, "message": message},
        ) as response:
            response.raise_for_status()
            event = "message"
            for line in response.iter_lines():
                if line.startswith("event:"):
                    event = line[len("event:") :].strip()
                elif line.startswith("data:"):
                    chunk = line[len("data:") :]
                    if chunk.startswith(" "):
                        chunk = chunk[1:]
                    yield event, chunk
                    event = "message"

    def get_history(self, session_id: str) -> dict[str, Any]:
        response = self._client.get(f"/chat/{session_id}/history")
        response.raise_for_status()
        return response.json()

    def get_logs(
        self,
        session_id: str,
        *,
        level: str | None = None,
        logger: str | None = None,
        start_time: str | None = None,
        end_time: str | None = None,
        limit: int = 200,
        offset: int = 0,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        if level:
            params["level"] = level
        if logger:
            params["logger"] = logger
        if start_time:
            params["start_time"] = start_time
        if end_time:
            params["end_time"] = end_time
        response = self._client.get(f"/chat/{session_id}/logs", params=params)
        response.raise_for_status()
        return response.json()

    def list_sessions(self) -> dict[str, Any]:
        response = self._client.get("/chat/sessions")
        response.raise_for_status()
        return response.json()

    def close(self) -> None:
        self._client.close()
