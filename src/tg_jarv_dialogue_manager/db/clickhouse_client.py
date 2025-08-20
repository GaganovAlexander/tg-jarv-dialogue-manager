from typing import Any, Dict, List, Optional

import httpx


class ClickHouseClient:
    def __init__(self, url: str, database: str, user: Optional[str] = None, password: Optional[str] = None, timeout: float = 30.0):
        self.url = url.rstrip("/")
        self.database = database
        self.user = user
        self.password = password
        self._client: Optional[httpx.AsyncClient] = None
        self._timeout = timeout

    async def _ensure(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self._timeout)
        return self._client

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    async def select(self, sql: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        client = await self._ensure()
        q = f"{sql} FORMAT JSONEachRow"
        params = params or {}
        params = {k: str(v) for k, v in params.items()}
        auth = None
        if self.user is not None and self.password is not None:
            auth = (self.user, self.password)
        r = await client.post(self.url, params={"database": self.database, **params}, content=q.encode("utf-8"), auth=auth)
        r.raise_for_status()
        lines = [line for line in r.text.splitlines() if line.strip()]
        out: List[Dict[str, Any]] = []
        import json as _json
        for line in lines:
            out.append(_json.loads(line))
        return out

    async def execute(self, sql: str) -> None:
        client = await self._ensure()
        auth = None
        if self.user is not None and self.password is not None:
            auth = (self.user, self.password)
        r = await client.post(self.url, params={"database": self.database}, content=sql.encode("utf-8"), auth=auth)
        r.raise_for_status()

def escape_str(value: str) -> str:
    return value.replace("\\", "\\\\").replace("'", "\\'")

def lit(value: Any) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, (int, float)):
        return str(value)
    return "'" + escape_str(str(value)) + "'"
