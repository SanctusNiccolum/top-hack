"""ТЕСТОВЫЙ вспомогательный скрипт — не часть парсера и не для прода.

Печатает список ваших диалогов (ЛС/группы/каналы) с их chat_id — чтобы
было что подставить в JSON-вход парсера, не гадая на глаз.

Запускать локально:

    pip install telethon
    python list_chats.py
"""
import asyncio

from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.tl.types import Channel, Chat, User


def guess_type(entity) -> str:
    """Грубая подсказка, какой `type` поставить в JSON-входе парсера —
    финальное решение всё равно за вами (см. README про own_messages/subscription).
    """
    if isinstance(entity, (User, Chat)):
        return "own_messages"          # ЛС или обычная группа
    if isinstance(entity, Channel):
        return "own_messages" if entity.megagroup else "subscription"
    return "unknown"


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
        print(f"\n{'chat_id':>16}  {'подсказка type':<14}  {'username':<20}  title")
        print("-" * 90)
        async for dialog in client.iter_dialogs():
            kind = guess_type(dialog.entity)
            username = getattr(dialog.entity, "username", None) or ""
            print(f"{dialog.id:>16}  {kind:<14}  {username:<20}  {dialog.name}")
    finally:
        await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
