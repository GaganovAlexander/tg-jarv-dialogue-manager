from typing import Optional, List, Dict, Any

from .jarv_client import JarvClient
from ..db.chat_storage import ChatStorage
from ..db.clickhouse_client import ClickHouseClient


class JarvDialogManager:
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
        table: str = "dialog_history",
        system_prompt: Optional[str] = None,
        pairs_limit: int = 10,
        char_soft_limit: int = 8000,
        payload_base: Optional[Dict[str, Any]] = None,
    ):
        self.bot_name = bot_name
        self.model = model
        self.user_id = user_id
        self.system_prompt = system_prompt
        self.pairs_limit = pairs_limit
        self.char_soft_limit = char_soft_limit
        self.payload_base = payload_base or {}
        self.jarv = JarvClient(api_key=jarv_api_key, endpoint=jarv_endpoint)
        self._ch = ClickHouseClient(url=clickhouse_url, database=clickhouse_database, user=clickhouse_user, password=clickhouse_password)
        self._storage = ChatStorage(self._ch, table=table, auto_create=True)

    def _parse_response(self, resp: Dict[str, Any]) -> str:
        if "answer" in resp and isinstance(resp["answer"], str):
            return resp["answer"]
        if "content" in resp and isinstance(resp["content"], str):
            return resp["content"]
        if "choices" in resp and resp["choices"] and "message" in resp["choices"][0] and "content" in resp["choices"][0]["message"]:
            return str(resp["choices"][0]["message"]["content"])
        return str(resp)

    def _make_payload(self, history: List[Dict[str, str]]) -> Dict[str, Any]:
        payload = dict(self.payload_base)
        payload["model"] = self.model
        payload["user"] = self.user_id
        messages: List[Dict[str, str]] = []
        if self.system_prompt:
            messages.append({"role": "system", "content": self.system_prompt})
        messages += history
        payload["messages"] = messages
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
            {"tg_id": tg_id, "bot_name": self.bot_name, "seq_in_dialog": user_seq, "role": "user", "content": user_text},
            {"tg_id": tg_id, "bot_name": self.bot_name, "seq_in_dialog": assistant_seq, "role": "assistant", "content": response_text},
        ])
        return response_text

    async def close(self) -> None:
        await self.jarv.close()
        await self._ch.close()
