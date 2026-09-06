"""ТЕСТОВЫЙ dev-инструмент — не часть парсера и не для прода.

Всё в одном месте: логин (спрашивает только номер и код — api_id/api_hash
берутся из переменных окружения), опциональное сохранение сессии между
запусками ЭТОГО скрипта, список ваших чатов, выбор chat_id прямо в
консоли, сборка JSON-входа, запуск парсера через `docker compose run` и
автоматическая проверка результата в Postgres.

НАСТРОЙКА (один раз, не при каждом запуске):

    Windows PowerShell, только на текущее окно терминала:
        $env:TG_API_ID = "12345"
        $env:TG_API_HASH = "abcdef0123456789abcdef0123456789"

    Windows — навсегда (потребует открыть новое окно терминала после):
        setx TG_API_ID "12345"
        setx TG_API_HASH "abcdef0123456789abcdef0123456789"

    macOS/Linux (добавить в ~/.bashrc или ~/.zshrc):
        export TG_API_ID=12345
        export TG_API_HASH=abcdef0123456789abcdef0123456789

ЗАПУСК (из папки telegram_parser/, где лежит docker-compose.yml):

    pip install telethon
    python dev_tools/run_test.py

Postgres должен быть уже поднят (`docker compose up -d postgres`), образ
парсера собран (`docker compose build parser`) — этот скрипт их не
поднимает и не собирает сам, только использует.
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
SESSION_CACHE = HERE / ".session_cache"  # только для удобства ЭТОГО скрипта,
                                          # к самому парсеру отношения не имеет


def guess_type(entity) -> str:
    """Грубая подсказка типа чата — финальное решение всё равно за вами."""
    if isinstance(entity, (User, Chat)):
        return "own_messages"
    if isinstance(entity, Channel):
        return "own_messages" if entity.megagroup else "subscription"
    return "own_messages"


def get_api_credentials() -> tuple[int, str]:
    api_id = os.environ.get("TG_API_ID")
    api_hash = os.environ.get("TG_API_HASH")
    if not api_id or not api_hash:
        print("Не заданы TG_API_ID / TG_API_HASH в переменных окружения.\n")
        print("PowerShell (на текущее окно терминала):")
        print('  $env:TG_API_ID = "12345"')
        print('  $env:TG_API_HASH = "abcdef..."\n')
        print("Или навсегда (нужно новое окно терминала после):")
        print('  setx TG_API_ID "12345"')
        print('  setx TG_API_HASH "abcdef..."')
        sys.exit(1)
    return int(api_id), api_hash


async def get_session(api_id: int, api_hash: str) -> str:
    if SESSION_CACHE.exists():
        answer = input(
            f"Найдена сохранённая сессия ({SESSION_CACHE.name}). Использовать? [Y/n]: "
        ).strip().lower()
        if answer in ("", "y", "yes", "д", "да"):
            return SESSION_CACHE.read_text().strip()

    client = TelegramClient(StringSession(), api_id, api_hash)
    await client.start()  # спросит номер телефона, код, при необходимости 2FA
    try:
        session_string = client.session.save()
    finally:
        await client.disconnect()

    answer = input(
        "Сохранить сессию для СЛЕДУЮЩИХ запусков этого скрипта? "
        "(сам парсер всё равно одноразовый — это только для вашего удобства, "
        "чтобы не логиниться каждый раз заново ради списка чатов) [y/N]: "
    ).strip().lower()
    if answer in ("y", "yes", "д", "да"):
        SESSION_CACHE.write_text(session_string)
        print(f"Сохранено в {SESSION_CACHE}")

    return session_string


async def list_dialogs(api_id: int, api_hash: str, session_string: str) -> None:
    client = TelegramClient(StringSession(session_string), api_id, api_hash)
    await client.connect()
    if not await client.is_user_authorized():
        print("Сессия не авторизована. Удалите файл кэша сессии "
              f"({SESSION_CACHE}) и запустите скрипт заново.")
        sys.exit(1)
    try:
        print(f"\n{'chat_id':>16}  {'подсказка type':<14}  {'username':<20}  title")
        print("-" * 90)
        async for dialog in client.iter_dialogs():
            kind = guess_type(dialog.entity)
            username = getattr(dialog.entity, "username", None) or ""
            print(f"{dialog.id:>16}  {kind:<14}  {username:<20}  {dialog.name}")
    finally:
        await client.disconnect()


def ask_chats() -> list[dict]:
    raw = input("\nВведите chat_id через запятую (из таблицы выше или уже известные вам): ").strip()
    chat_ids = [x.strip() for x in raw.split(",") if x.strip()]
    chats = []
    for cid in chat_ids:
        t = input(f"  Тип для {cid} [own_messages/subscription, Enter = own_messages]: ").strip()
        chats.append({"chat_id": int(cid), "type": t or "own_messages"})
    return chats


def run_parser(payload: dict) -> int:
    print("\nЗапускаю парсер через docker compose...\n")
    try:
        proc = subprocess.run(
            ["docker", "compose", "run", "--rm", "-T", "parser"],
            input=json.dumps(payload).encode("utf-8"),
            cwd=PROJECT_ROOT,
        )
    except FileNotFoundError:
        print("Не нашёл команду docker — проверьте, что Docker Desktop запущен "
              "и docker доступен из этого терминала.")
        sys.exit(1)
    return proc.returncode


def check_results(user_id: int) -> None:
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
    session_string = await get_session(api_id, api_hash)

    await list_dialogs(api_id, api_hash, session_string)

    chats = ask_chats()
    if not chats:
        print("Ни одного chat_id не введено — выход.")
        return

    user_id_raw = input("user_id для теста [Enter = 1]: ").strip()
    user_id = int(user_id_raw) if user_id_raw else 1

    payload = {
        "user_id": user_id,
        "session_string": session_string,
        "api_id": api_id,
        "api_hash": api_hash,
        "chats": chats,
    }

    code = run_parser(payload)
    print(f"\nПарсер завершился с кодом {code}.")

    # Парсер вызывает log_out() при ЛЮБОМ исходе — сохранённая сессия (если
    # была) теперь мертва в любом случае. Удаляем кэш, чтобы в следующий
    # раз скрипт не предложил использовать уже недействительную сессию.
    if SESSION_CACHE.exists():
        SESSION_CACHE.unlink()
        print("Сессия только что использована парсером и им же инвалидирована "
              "(log_out() внутри main.py) — локальный кэш сессии удалён, "
              "в следующий раз потребуется новый логин.")

    check_results(user_id)


if __name__ == "__main__":
    asyncio.run(main())
