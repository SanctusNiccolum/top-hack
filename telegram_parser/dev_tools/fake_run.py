"""ТЕСТОВЫЙ dev-инструмент — прогон реальной логики парсера (db.py,
cleaning.py, telegram_client.py, main.py) на фейковых Telegram-данных, без
единого обращения к серверам Telegram. Нужен настоящий Postgres.

Запуск (Postgres из docker-compose уже поднят и слушает localhost:5432):
    DATABASE_URL="postgresql://parser:parser@localhost:5432/parser_db" \\
        python dev_tools/fake_run.py
"""
import asyncio
import os
import sys
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from telegram_parser import db  # noqa: E402
from telegram_parser.main import _process_chat  # noqa: E402

ME_ID = 5270187642  # реальный тип ID, как у настоящих аккаунтов
OWN_CHAT_ID = -100111111
SUB_CHAT_ID = -100222222
NOW = datetime.now(timezone.utc)


def _msg(id, days_ago, sender_id, text, forward=None, reply_to=None):
    return SimpleNamespace(
        id=id, date=NOW - timedelta(days=days_ago), sender_id=sender_id,
        raw_text=text, forward=forward, reply_to=reply_to,
    )


class FakeEntityChat:
    title = None
    first_name = "Тестовый личный чат"


class FakeEntityChannel:
    title = "Финансовые лайфхаки (фейк)"
    username = "fake_finance_channel"


class FakeClient:
    async def get_dialogs(self):
        return []

    async def get_entity(self, chat_id):
        return FakeEntityChannel() if chat_id == SUB_CHAT_ID else FakeEntityChat()

    async def iter_messages(self, chat_id):
        if chat_id != OWN_CHAT_ID:
            return  # подписка на канал — пользователь тут не пишет, это реалистично
        for m in [
            _msg(1, 1, ME_ID, "у меня сейчас всё стабильно с проектами и доходом"),
            _msg(2, 2, 999999, "чужое сообщение — не должно попасть в выборку"),
            _msg(3, 3, ME_ID, "ок"),  # короткое — теперь ОСТАЁТСЯ (фильтр убран)
            _msg(4, 5, ME_ID, "три месяца назад были проблемы с деньгами", forward=object()),
            _msg(5, 8, ME_ID, "мой телефон +7 921 555-12-34, звони если срочно"),  # PII
        ]:
            yield m

    async def __call__(self, request):
        return SimpleNamespace(full_chat=SimpleNamespace(about="Тестовый канал про финансы"))

    async def log_out(self):
        pass

    async def disconnect(self):
        pass


async def main() -> None:
    if "DATABASE_URL" not in os.environ:
        print("Задайте DATABASE_URL (например, Postgres из docker-compose на localhost:5432)")
        return

    pool = await db.get_pool()
    client = FakeClient()

    for chat_id in (OWN_CHAT_ID, SUB_CHAT_ID):
        await _process_chat(client, pool, ME_ID, ME_ID, chat_id)

    await db.enqueue_ai(pool, ME_ID, status="pending")
    await pool.close()

    print(f"Готово. Данные записаны под user_id={ME_ID}. Проверьте через psql:\n")
    print(f"  SELECT * FROM parse_state WHERE user_id={ME_ID};")
    print(f"  SELECT tg_msg_id, text FROM messages WHERE user_id={ME_ID};")
    print(f"  SELECT * FROM subscriptions WHERE user_id={ME_ID};")


if __name__ == "__main__":
    asyncio.run(main())
