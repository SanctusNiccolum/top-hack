"""Импорт данных из официального экспорта Telegram Desktop (result.json),
как альтернатива live-парсингу через Telethon.

Причина существования: получить api_id/api_hash для Telethon сейчас
физически не выходит (антифрод my.telegram.org режет российские номера
через VPN, а без VPN сайт недоступен). Экспорт Telegram Desktop даёт
почти тот же набор данных (свои сообщения + список чатов/каналов) без
единого обращения к Telegram API — только чтение файла, который
пользователь сам выгрузил через официальное приложение.

Формат result.json — см. https://core.telegram.org/import-export.
Ключевая деталь оттуда: "public group and channel exports will only
contain messages sent by the user requesting the export" — то есть для
public_supergroup Telegram уже сам отфильтровал чужие сообщения; для
personal_chat/private_group/private_supergroup фильтрацию по автору
всё равно делаем сами (там экспортируются ОБЕ стороны переписки).

ЧТО ТЕРЯЕТСЯ по сравнению с live-версией (main.py):
- У Chat в экспорте нет полей username/about — сверка подписок с
  trusted_channels (по username) невозможна, trusted_channel_id всегда
  NULL, about всегда NULL. Это ограничение формата экспорта, не баг.
"""
from __future__ import annotations

from datetime import datetime, timezone

from .cleaning import clean_message_text

# Как классифицируем typeMi из экспорта в наши own_messages/subscription.
# Каналы — подписка (метаданные), всё остальное — свои сообщения.
_SUBSCRIPTION_TYPES = {"private_channel", "public_channel"}
_OWN_MESSAGE_TYPES = {
    "saved_messages", "replies", "personal_chat", "bot_chat",
    "private_group", "private_supergroup", "public_supergroup",
}


def classify_chat_type(export_type: str) -> str:
    """own_messages | subscription | unknown"""
    if export_type in _SUBSCRIPTION_TYPES:
        return "subscription"
    if export_type in _OWN_MESSAGE_TYPES:
        return "own_messages"
    return "unknown"


def extract_text(message: dict) -> str:
    """`text` в экспорте — либо строка, либо список (строки вперемешку с
    {"type": ..., "text": ...} для форматированных кусков). `text_entities`
    всегда список той же природы — с ним проще, используем его.
    """
    entities = message.get("text_entities")
    if entities:
        return "".join(e.get("text", "") for e in entities)

    text = message.get("text", "")
    if isinstance(text, str):
        return text
    if isinstance(text, list):
        return "".join(
            part if isinstance(part, str) else part.get("text", "")
            for part in text
        )
    return ""


def _parse_export_date(message: dict) -> datetime | None:
    raw = message.get("date_unixtime")
    if raw is not None:
        return datetime.fromtimestamp(int(raw), tz=timezone.utc)
    date_str = message.get("date")
    if date_str:
        return datetime.fromisoformat(date_str).replace(tzinfo=timezone.utc)
    return None


def extract_own_messages(chat: dict, owner_user_id: int, since_date: datetime) -> list[dict]:
    """Сообщения самого пользователя из одного chat-объекта экспорта."""
    owner_from_id = f"user{owner_user_id}"
    collected = []

    for msg in chat.get("messages", []):
        if msg.get("type") != "message":
            continue  # служебные события (кто-то зашёл/вышел и т.п.) — не текст

        msg_date = _parse_export_date(msg)
        if msg_date is None or msg_date < since_date:
            continue

        if msg.get("from_id") != owner_from_id:
            continue  # не наш пользователь написал (для public_* экспорт и так уже отфильтрован)

        cleaned = clean_message_text(extract_text(msg))
        if cleaned is None:
            continue

        collected.append({
            "tg_msg_id": msg["id"],
            "datetime": msg_date,
            "text": cleaned,
            "is_forward": "forwarded_from" in msg,
            "is_reply": "reply_to_message_id" in msg,
        })

    return collected


def extract_subscription_meta(chat: dict) -> dict:
    """username/about в экспорте отсутствуют в принципе — см. docstring модуля."""
    return {
        "channel_name": chat.get("name"),
        "username": None,
        "about": None,
    }
