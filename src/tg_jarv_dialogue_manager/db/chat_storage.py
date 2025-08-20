from typing import Iterable, List, Dict

from .clickhouse_client import ClickHouseClient, lit


class ChatStorage:
    def __init__(self, ch: ClickHouseClient, table: str, auto_create: bool = True):
        self.ch = ch
        self.table = table
        self.auto_create = auto_create
        self._schema_ensured = False

    async def ensure_schema(self) -> None:
        if self._schema_ensured or not self.auto_create:
            self._schema_ensured = True
            return
        sql = f"""
        CREATE TABLE IF NOT EXISTS {self.table} (
          tg_id UInt64,
          bot_name String,
          seq_in_dialogue UInt32,
          role LowCardinality(String),
          content String,
          created_at DateTime DEFAULT now()
        ) ENGINE = MergeTree
        ORDER BY (tg_id, bot_name, seq_in_dialogue)
        TTL created_at + INTERVAL 14 DAY;
        """
        await self.ch.execute(sql)
        self._schema_ensured = True

    async def next_seq(self, tg_id: int) -> int:
        await self.ensure_schema()
        rows = await self.ch.select(f"""
            SELECT max(seq_in_dialogue) AS mx
            FROM {self.table}
            WHERE tg_id = {tg_id}
        """)
        if not rows or rows[0]["mx"] is None:
            return 1
        return int(rows[0]["mx"]) + 1

    async def append_messages(self, rows: Iterable[Dict[str, str]]) -> None:
        await self.ensure_schema()
        values = []
        for r in rows:
            values.append(f"({r['tg_id']}, {lit(r['bot_name'])}, {r['seq_in_dialogue']}, {lit(r['role'])}, {lit(r['content'])})")
        sql = f"""
        INSERT INTO {self.table} (tg_id, bot_name, seq_in_dialogue, role, content)
        VALUES {', '.join(values)}
        """
        await self.ch.execute(sql)

    async def build_recent_history(self, tg_id: int, pairs_limit: int, char_soft_limit: int) -> List[Dict[str, str]]:
        await self.ensure_schema()
        rows = await self.ch.select(f"""
            SELECT role, content
            FROM {self.table}
            WHERE tg_id = {tg_id}
            ORDER BY seq_in_dialogue DESC
            LIMIT {pairs_limit * 2}
        """)
        rows = list(reversed(rows))
        msgs: List[Dict[str, str]] = []
        total = 0
        for r in rows:
            c = str(r["content"])
            if total + len(c) > char_soft_limit and msgs:
                break
            msgs.append({"role": r["role"], "content": c})
            total += len(c)
        return msgs
