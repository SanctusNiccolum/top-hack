"""ТЕСТОВЫЙ вспомогательный скрипт — не часть парсера и не для прода.

Интерактивно логинится в Telegram (спросит номер телефона, код из
Telegram и, если включена, 2FA-пароль) и печатает session_string, который
дальше используется как вход для telegram_parser.

Запускать ЛОКАЛЬНО (не в Docker) — нужен интерактивный терминал для ввода
кода:

    pip install telethon
    python get_session.py

api_id/api_hash берутся один раз на https://my.telegram.org -> API
development tools. Это данные ВАШЕГО приложения, не конкретного
пользователя — одна и та же пара api_id/api_hash используется для логина
любого аккаунта.
"""
import asyncio

from telethon import TelegramClient
from telethon.sessions import StringSession


async def main() -> None:
    api_id = int(input("api_id: ").strip())
    api_hash = input("api_hash: ").strip()

    client = TelegramClient(StringSession(), api_id, api_hash)
    await client.start()  # спросит номер телефона, код, при необходимости 2FA
    try:
        me = await client.get_me()
        print(f"\nЗалогинены как: {me.first_name} (id={me.id})\n")
        print("session_string (сохраните — понадобится для JSON-входа парсера):\n")
        print(client.session.save())
    finally:
        await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
