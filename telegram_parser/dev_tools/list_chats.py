"""ТЕСТОВЫЙ вспомогательный скрипт — не часть парсера и не для прода.

Печатает список ваших диалогов (ЛС/группы/каналы) с их chat_id — чтобы
было что подставить в JSON-вход парсера (поле chat_ids), не гадая на глаз.
Тип чата теперь не нужен — main.py сам пробует оба метода на любой chat_id.

Запускать локально:
    pip install telethon
    python list_chats.py
"""
import asyncio

from telethon import TelegramClient
from telethon.sessions import StringSession


async def main() -> None:
    api_id = int(input("api_id: ").strip())
    api_hash = input("api_hash: ").strip()
    session_string = input("session_string (из get_session.py): ").strip()

    client = TelegramClient(StringSession(session_string), api_id, api_hash)
    await client.connect()
    if not await client.is_user_authorized():
        print("Сессия не авторизована — получите новую через get_session.py")
        return

    try:
        print(f"\n{'chat_id':>16}  {'username':<20}  title")
        print("-" * 80)
        async for dialog in client.iter_dialogs():
            username = getattr(dialog.entity, "username", None) or ""
            print(f"{dialog.id:>16}  {username:<20}  {dialog.name}")
    finally:
        await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
