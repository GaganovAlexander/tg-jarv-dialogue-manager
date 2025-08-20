from typing import Any, Dict, Optional

import httpx


class JarvClient:
    def __init__(self, api_key: str, endpoint: str, client: Optional[httpx.AsyncClient] = None, timeout: float = 60.0):
        self.api_key = api_key
        self.endpoint = endpoint
        self._ext = client
        self._client: Optional[httpx.AsyncClient] = None
        self._timeout = timeout

    async def _ensure(self) -> httpx.AsyncClient:
        if self._ext:
            return self._ext
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self._timeout)
        return self._client

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    async def chat(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        client = await self._ensure()
        headers = {"api-key": self.api_key, "Content-Type": "application/json"}
        resp = await client.post(self.endpoint, headers=headers, json=payload)
        resp.raise_for_status()
        return resp.json()
