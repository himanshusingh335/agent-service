from collections.abc import Iterator

import httpx


class AgentServiceClient:
    def __init__(self, base_url: str):
        self._base_url = base_url.rstrip("/")
        self._client = httpx.Client(base_url=self._base_url, timeout=60.0)

    def invoke(self, session_id: str, message: str) -> str:
        response = self._client.post(
            "/chat/invoke", json={"session_id": session_id, "message": message}
        )
        response.raise_for_status()
        return response.json()["reply"]

    def stream(self, session_id: str, message: str) -> Iterator[str]:
        with self._client.stream(
            "POST",
            "/chat/stream",
            json={"session_id": session_id, "message": message},
        ) as response:
            response.raise_for_status()
            for line in response.iter_lines():
                if line.startswith("data:"):
                    chunk = line[len("data:") :]
                    if chunk.startswith(" "):
                        chunk = chunk[1:]
                    yield chunk

    def close(self) -> None:
        self._client.close()
