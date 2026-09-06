"""ТЕСТОВЫЙ dev-инструмент — не часть парсера и не для прода.

Логин (только номер+код — api_id/api_hash из переменных окружения),
список ваших чатов, выбор chat_id прямо в консоли, запуск парсера через
`docker compose run` и проверка результата в БД — всё за один вызов.

Сессия всегда новая при каждом запуске (не кэшируется) — как и сам
парсер, это одноразовый вход. user_id НЕ вводится вручную — берётся
автоматически из вашего собственного Telegram-аккаунта (тот же me.id,
что использует main.py), чтобы не плодить случайные тестовые ID.

НАСТРОЙКА (один раз, не при каждом запуске):
    Windows PowerShell (на текущее окно терминала):
        $env:TG_API_ID = "12345"
        $env:TG_API_HASH = "abcdef..."
    Windows — навсегда (нужно новое окно терминала после):
        setx TG_API_ID "12345"
        setx TG_API_HASH "abcdef..."

ЗАПУСК (из папки telegram_parser/, где лежит docker-compose.yml):
    pip install telethon
    python dev_tools/run_test.py

Postgres должен быть уже поднят (`docker compose up -d postgres`), образ
парсера собран (`docker compose build parser`).
"""
from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path

from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.tl.types import Channel, Chat, User

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parent  # там лежит docker-compose.yml


def get_api_credentials() -> tuple[int, str]:
    api_id = os.environ.get("TG_API_ID")
    api_hash = os.environ.get("TG_API_HASH")
    if not api_id or not api_hash:
        print("Не заданы TG_API_ID / TG_API_HASH в переменных окружения.\n")
        print("PowerShell (на текущее окно терминала):")
        print('  $env:TG_API_ID = "12345"')
        print('  $env:TG_API_HASH = "abcdef..."')
        sys.exit(1)
    return int(api_id), api_hash


async def login_and_list_dialogs(api_id: int, api_hash: str) -> tuple[str, int]:
    """Логинится (спросит номер+код), возвращает (session_string, me_id) и
    попутно печатает список диалогов с их chat_id.
    """
    client = TelegramClient(StringSession(), api_id, api_hash)
    await client.start()  # спросит номер телефона, код, при необходимости 2FA
    try:
        me = await client.get_me()
        session_string = client.session.save()

        print(f"\nЗалогинены как: {me.first_name} (id={me.id})")
        print(f"\n{'chat_id':>16}  {'username':<20}  title")
        print("-" * 80)
        async for dialog in client.iter_dialogs():
            username = getattr(dialog.entity, "username", None) or ""
            print(f"{dialog.id:>16}  {username:<20}  {dialog.name}")

        return session_string, me.id
    finally:
        await client.disconnect()


def ask_chat_ids() -> list[int]:
    raw = input("\nВведите chat_id через запятую (из таблицы выше или уже известные вам): ").strip()
    return [int(x.strip()) for x in raw.split(",") if x.strip()]


def run_parser(payload: dict) -> int:
    print("\nЗапускаю парсер через docker compose...\n")
    try:
        proc = subprocess.run(
            ["docker", "compose", "run", "--rm", "-T", "parser"],
            input=json.dumps(payload).encode("utf-8"),
            cwd=PROJECT_ROOT,
        )
    except FileNotFoundError:
        print("Не нашёл команду docker — проверьте, что Docker Desktop запущен.")
        sys.exit(1)
    return proc.returncode


def export_texts(user_id: int) -> None:
    # Через docker compose run, а не напрямую asyncpg с Windows — так это
    # соединение с Postgres идёт изнутри контейнера (тот же принцип, что и
    # в check_results выше), а не с голого Windows-хоста, где asyncpg
    # иногда упирается в известную проблему ProactorEventLoop (WinError 64).
    print(f"\nЭкспортирую тексты пользователя {user_id} в плоский JSON...\n")
    subprocess.run(
        ["docker", "compose", "run", "--rm", "--entrypoint", "python", "parser",
         "-m", "telegram_parser.export_texts", str(user_id)],
        cwd=PROJECT_ROOT,
    )
    print("\nПроверяю результат в БД...\n")
    queries = [
        f"SELECT chat_id, status, error_message FROM parse_state WHERE user_id={user_id};",
        f"SELECT tg_msg_id, text, is_forward, is_reply FROM messages WHERE user_id={user_id};",
        f"SELECT chat_id, username, about, trusted_channel_id FROM subscriptions WHERE user_id={user_id};",
        f"SELECT status FROM ai_queue WHERE user_id={user_id} ORDER BY created_at DESC LIMIT 1;",
    ]
    for q in queries:
        subprocess.run(
            ["docker", "compose", "exec", "-T", "postgres",
             "psql", "-U", "parser", "-d", "parser_db", "-c", q],
            cwd=PROJECT_ROOT,
        )


async def main() -> None:
    api_id, api_hash = get_api_credentials()
    session_string, me_id = await login_and_list_dialogs(api_id, api_hash)

    chat_ids = ask_chat_ids()
    if not chat_ids:
        print("Ни одного chat_id не введено — выход.")
        return

    payload = {
        "session_string": session_string,
        "api_id": api_id,
        "api_hash": api_hash,
        "chat_ids": chat_ids,
    }

    code = run_parser(payload)
    print(f"\nПарсер завершился с кодом {code}.")
    print("Сессия только что использована и инвалидирована самим парсером "
          "(log_out() внутри main.py) — при следующем запуске потребуется новый логин.")

    check_results(me_id)
    export_texts(me_id)


if __name__ == "__main__":
    asyncio.run(main())
