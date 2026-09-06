"""ТЕСТОВЫЙ dev-инструмент — не часть парсера и не для прода.

Прогоняет РЕАЛЬНУЮ логику парсера (db.py, cleaning.py, telegram_client.py,
main._process_chat) на заранее заготовленных фейковых Telegram-сообщениях.
Ни одного реального обращения к серверам Telegram не происходит — нужен
только настоящий Postgres (например, поднятый через docker compose).

Существует, чтобы можно было проверить связку "код + Postgres + Docker" не
разбираясь параллельно с логином в Telegram — если тут всё пройдёт, а с
реальным Telegram что-то не получается, значит проблема именно в
логине/сессии/сети до Telegram, а не в парсере или БД.

Запуск (Postgres из docker-compose уже поднят и слушает localhost:5432):

    cd telegram_parser
    pip install -r requirements.txt
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

FAKE_USER_ID = 1
ME_ID = 555
OWN_CHAT_ID = -100111111
SUB_CHAT_ID = -100222222

NOW = datetime.now(timezone.utc)


def _msg(id, days_ago, sender_id, text, forward=None, reply_to=None):
    return SimpleNamespace(
        id=id,
        date=NOW - timedelta(days=days_ago),
        sender_id=sender_id,
        raw_text=text,
        forward=forward,
        reply_to=reply_to,
    )


class FakeEntityChat:
    title = "Тестовый личный чат"
    first_name = None


class FakeEntityChannel:
    title = "Финансовые лайфхаки (фейк)"
    username = "fake_finance_channel"


class FakeFullChat:
    about = "Тестовый канал про финансы — сгенерирован fake_run.py"


class FakeFull:
    full_chat = FakeFullChat()


class FakeClient:
    """Имитирует ровно тот интерфейс TelegramClient, который использует
    telegram_client.py. Реального сетевого обращения к Telegram нет.
    """

    async def get_dialogs(self):
        return []

    async def get_entity(self, chat_id):
        return FakeEntityChannel() if chat_id == SUB_CHAT_ID else FakeEntityChat()

    async def iter_messages(self, chat_id):
        messages = [
            _msg(1, 1, ME_ID, "у меня сейчас всё стабильно с проектами и доходом"),
            _msg(2, 2, 999999, "а у меня наоборот сплошные проблемы с деньгами"),  # чужое — отсеется
            _msg(3, 3, ME_ID, "ок"),  # короткое — отсеется
            _msg(4, 5, ME_ID, "три месяца назад были проблемы с деньгами", forward=object()),
            _msg(5, 7, ME_ID, "отвечаю на вопрос про доход за прошлый месяц", reply_to=object()),
            _msg(6, 8, ME_ID, "мой телефон +7 921 555-12-34, звони если что срочное"),  # PII
        ]
        for m in messages:
            yield m

    async def __call__(self, request):
        return FakeFull()

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

    chats = [
        {"chat_id": OWN_CHAT_ID, "type": "own_messages"},
        {"chat_id": SUB_CHAT_ID, "type": "subscription"},
    ]

    for chat in chats:
        await _process_chat(client, pool, FAKE_USER_ID, ME_ID, chat)

    await db.enqueue_ai(pool, FAKE_USER_ID, status="pending")
    await pool.close()

    print(f"Готово. Данные записаны под user_id={FAKE_USER_ID}. Проверьте через psql:\n")
    print(f"  SELECT * FROM parse_state WHERE user_id={FAKE_USER_ID};")
    print(f"  SELECT tg_msg_id, text, is_forward, is_reply FROM messages WHERE user_id={FAKE_USER_ID};")
    print(f"  SELECT * FROM subscriptions WHERE user_id={FAKE_USER_ID};")
    print(f"  SELECT * FROM ai_queue WHERE user_id={FAKE_USER_ID};")


if __name__ == "__main__":
    asyncio.run(main())
