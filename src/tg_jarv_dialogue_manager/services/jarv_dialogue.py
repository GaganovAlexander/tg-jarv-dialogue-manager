from typing import Optional, List, Dict, Any

from .jarv_client import JarvClient
from ..db.chat_storage import ChatStorage
from ..db.clickhouse_client import ClickHouseClient


class JarvDialogueManager:
    def __init__(
        self,
        *,
        bot_name: str,
        model: str,
        user_id: str,
        jarv_api_key: str,
        jarv_endpoint: str,
        clickhouse_url: str,
        clickhouse_database: str,
        clickhouse_user: Optional[str] = None,
        clickhouse_password: Optional[str] = None,
        table: str = "dialogue_history",
        pairs_limit: int = 10,
        char_soft_limit: int = 8000,
        payload_base: Optional[Dict[str, Any]] = None,
    ):
        self.bot_name = bot_name
        self.model = model
        self.user_id = user_id
        self.pairs_limit = pairs_limit
        self.char_soft_limit = char_soft_limit
        self.payload_base = payload_base or {}
        self.jarv = JarvClient(api_key=jarv_api_key, endpoint=jarv_endpoint)
        self._ch = ClickHouseClient(url=clickhouse_url, database=clickhouse_database, user=clickhouse_user, password=clickhouse_password)
        self._storage = ChatStorage(self._ch, table=table, auto_create=True)

    def _parse_response(self, resp: Dict[str, Any]) -> str:
        if "response" in resp and "text" in resp["response"]:
            return resp["response"]["text"]
        return ""

    def _make_payload(self, history: List[Dict[str, str]]) -> Dict[str, Any]:
        payload = self.payload_base
        payload["model"] = self.model
        payload["user_id"] = self.user_id
        if history:
            payload["messages"] = history
        return payload

    async def build_history(self, tg_id: int) -> List[Dict[str, str]]:
        return await self._storage.build_recent_history(tg_id, self.pairs_limit, self.char_soft_limit)

    async def ask(self, tg_id: int, user_text: str) -> str:
        user_seq = await self._storage.next_seq(tg_id)
        assistant_seq = user_seq + 1
        history = await self.build_history(tg_id)
        payload = self._make_payload(history)
        payload["prompt"] = user_text
        resp = await self.jarv.chat(payload)
        response_text = self._parse_response(resp)
        await self._storage.append_messages([
            {"tg_id": tg_id, "bot_name": self.bot_name, "seq_in_dialogue": user_seq, "role": "user", "content": user_text},
            {"tg_id": tg_id, "bot_name": self.bot_name, "seq_in_dialogue": assistant_seq, "role": "assistant", "content": response_text},
        ])
        return response_text

    async def close(self) -> None:
        await self.jarv.close()
        await self._ch.close()
