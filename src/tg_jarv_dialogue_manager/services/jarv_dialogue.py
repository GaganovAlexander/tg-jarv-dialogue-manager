import logging
from typing import Optional, List, Dict, Any
from copy import deepcopy

from .jarv_client import JarvClient
from ..db.chat_storage import ChatStorage
from ..db.clickhouse_client import ClickHouseClient


logger = logging.getLogger(__name__)


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
        table_ttl_days: int = 14,
        pairs_limit: int = 10,
        char_soft_limit: int = 2000,
        payload_base: Optional[Dict[str, Any]] = None,
    ):
        self.bot_name = bot_name
        self.model = model
        self.user_id = user_id
        self.jarv_api_key = jarv_api_key
        self.pairs_limit = pairs_limit
        self.char_soft_limit = char_soft_limit
        self.payload_base = payload_base or {}
        self.jarv = JarvClient(api_key=jarv_api_key, endpoint=jarv_endpoint)
        self._ch = ClickHouseClient(
            url=clickhouse_url,
            database=clickhouse_database,
            user=clickhouse_user,
            password=clickhouse_password,
        )
        self._storage = ChatStorage(
            self._ch, table=table, ttl_days=table_ttl_days, auto_create=True
        )
        self._payload = self.payload_base
        self._payload["model"] = self.model
        self._payload["user_id"] = self.user_id

    def _parse_response(self, resp: Dict[str, Any]) -> str:
        if "response" in resp and "text" in resp["response"]:
            return resp["response"]["text"]
        return ""

    def _make_payload(self, history: List[Dict[str, str]]) -> Dict[str, Any]:
        payload = deepcopy(self._payload)
        if history:
            payload["messages"] = history
        return payload

    async def build_history(
        self, tg_id: int
    ) -> List[Dict[str, str]]:
        return await self._storage.build_recent_history(
            tg_id, self.bot_name, self.pairs_limit, self.char_soft_limit
        )

    async def ask(self, tg_id: int, user_text: str) -> str:
        user_seq = await self._storage.next_seq(tg_id, self.bot_name)
        assistant_seq = user_seq + 1
        history = await self.build_history(tg_id)
        payload = self._make_payload(history)
        payload["prompt"] = user_text

        logger.info(
            "[Jarv] Sending request | history=%d | last_prompt=%r | project_id=%s | user_id=%s | api_key=%s",
            len(history),
            user_text,
            (str(self._payload.get("project_id"))[-4:] if self._payload.get("project_id") else "none"),
            str(self.user_id)[-4:],
            str(self.jarv_api_key)[-4:],
        )

        resp = await self.jarv.chat(payload)
        response_text = self._parse_response(resp)

        usage = resp.get("usage", {})
        cost = resp.get("cost", {})
        logger.info(
            "[Jarv] Response received | tokens: %s | cost: %s %s",
            f"{usage.get('prompt_tokens',0)}+{usage.get('completion_tokens',0)}={usage.get('total_tokens',0)}",
            cost.get("total_cost_rub"),
            cost.get("currency"),
        )

        await self._storage.append_messages(
            [
                {
                    "tg_id": tg_id,
                    "bot_name": self.bot_name,
                    "seq_in_dialogue": user_seq,
                    "role": "user",
                    "content": user_text,
                },
                {
                    "tg_id": tg_id,
                    "bot_name": self.bot_name,
                    "seq_in_dialogue": assistant_seq,
                    "role": "assistant",
                    "content": response_text,
                },
            ]
        )
        return response_text

    async def close(self) -> None:
        await self.jarv.close()
        await self._ch.close()
