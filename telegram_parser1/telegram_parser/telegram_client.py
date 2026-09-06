"""Telethon-specific logic: fetching own messages and subscription metadata.

Kept separate from db.py and main.py so the Telegram-facing code doesn't
know anything about Postgres, and can be unit-tested with a fake/mock
client if needed.
"""
from __future__ import annotations

from datetime import datetime

from telethon import TelegramClient
from telethon.tl.functions.channels import GetFullChannelRequest

from .cleaning import clean_message_text


async def parse_own_messages(
    client: TelegramClient,
    chat_id: int,
    since_date: datetime,
    me_id: int,
) -> list[dict]:
    """Collect the account owner's own messages in a chat, from `since_date` onward.

    Includes messages the user forwarded into the chat: Telegram attributes
    the `from_id` of a forwarded message to whoever posted it into *this*
    chat, not to the original author — so a forward is, mechanically, the
    user's own action and passes the `sender_id == me_id` filter. It is kept
    but flagged via `is_forward` so the AI side can tell the user's own
    words apart from reposted content (e.g. forwarding a friend's message
    about financial trouble should not read as the user's own situation).
    """
    collected: list[dict] = []

    async for msg in client.iter_messages(chat_id):
        if msg.date is None:
            continue
        if msg.date < since_date:
            # Telethon returns messages newest-first by default, so once we
            # cross the lower bound of our window there's nothing older left
            # to check — stop instead of scanning the entire chat history.
            break
        if msg.sender_id != me_id:
            continue

        cleaned = clean_message_text(msg.raw_text)
        if cleaned is None:
            continue  # empty / sticker-only / too short after PII-scrubbing

        collected.append({
            "tg_msg_id": msg.id,
            "datetime": msg.date,
            "text": cleaned,
            "is_forward": msg.forward is not None,
            "is_reply": msg.reply_to is not None,
        })

    return collected


async def parse_subscription(client: TelegramClient, chat_id: int) -> dict:
    """Fetch title / username / description for a channel the user follows.

    `username` (the stable @handle) is what gets matched against
    trusted_channels — `channel_name` (the display title) is stored only
    for human reference, since a title can be changed by the channel owner
    at any time and can't be relied on for classification.
    """
    entity = await client.get_entity(chat_id)
    username = getattr(entity, "username", None)
    title = getattr(entity, "title", None)

    about = None
    try:
        full = await client(GetFullChannelRequest(entity))
        about = full.full_chat.about or None
    except Exception:
        # Not every entity supports GetFullChannelRequest (e.g. it turned
        # out to be a plain user/chat, not a channel) — `about` just stays
        # None in that case rather than failing the whole chat.
        pass

    return {"channel_name": title, "username": username, "about": about}
