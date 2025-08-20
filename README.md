# tg-jarv-dialogue-manager

Асинхронный клиент Jarv AI и диалог-менеджер с хранением истории в ClickHouse.

## Установка

```bash
pip install tg-jarv-dialogue-manager
```

Опционально для Telegram:
```bash
pip install "tg-jarv-dialogue-manager[telegram]"
```

## Быстрый старт

```python
import asyncio
from tg_jarv_dialogue_manager import JarvDialogueManager

async def main():
    dm = JarvDialogueManager(
        bot_name="DiscountBot",
        model="gpt-4o-mini",
        user_id="bot@synergetic",
        jarv_api_key="...",
        jarv_endpoint="https://api.jarv.tech/v1/chat",
        clickhouse_url="http://localhost:8123",
        clickhouse_database="jarv",
        clickhouse_user=None,
        clickhouse_password=None,
        table="dialogue_history",
        pairs_limit=10,
        char_soft_limit=2000,
        payload_base={"profect_id": "12abcd3e-4f5g-1111-aaaa-1111abc22de3"},
    )
    answer = await dm.ask(tg_id=123456789, user_text="Привет!")
    print(answer)
    await dm.close()

asyncio.run(main())
```

## Схема ClickHouse по умолчанию

```sql
CREATE TABLE IF NOT EXISTS dialogue_history (
  tg_id UInt64,
  bot_name String,
  seq_in_dialogue UInt32,
  role LowCardinality(String),
  content String,
  created_at DateTime DEFAULT now()
) ENGINE = MergeTree
ORDER BY (tg_id, bot_name, seq_in_dialogue);
```

## Поддержка

Issues и PR приветствуются.
