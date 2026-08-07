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

    def close(self) -> None:
        self._client.close()
