"""Тесты для import_parser.py — режима без Telegram API (по официальному
экспорту Telegram Desktop). Не трогают ни Telegram, ни реальный Postgres.
"""
import os
import sys
import unittest
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from telegram_parser.import_parser import (  # noqa: E402
    classify_chat_type,
    extract_own_messages,
    extract_subscription_meta,
    extract_text,
)

NOW = datetime.now(timezone.utc)
OWNER_ID = 999
OWNER_FROM_ID = f"user{OWNER_ID}"


def days_ago(n):
    return NOW - timedelta(days=n)


class ClassifyChatTypeTests(unittest.TestCase):
    def test_channels_are_subscriptions(self):
        self.assertEqual(classify_chat_type("private_channel"), "subscription")
        self.assertEqual(classify_chat_type("public_channel"), "subscription")

    def test_everything_else_known_is_own_messages(self):
        for t in ("saved_messages", "replies", "personal_chat", "bot_chat",
                  "private_group", "private_supergroup", "public_supergroup"):
            self.assertEqual(classify_chat_type(t), "own_messages", t)

    def test_unknown_type(self):
        self.assertEqual(classify_chat_type("something_new_telegram_added"), "unknown")


class ExtractTextTests(unittest.TestCase):
    def test_plain_string(self):
        self.assertEqual(extract_text({"text": "привет мир"}), "привет мир")

    def test_list_of_strings_and_entity_dicts(self):
        msg = {"text": ["привет ", {"type": "bold", "text": "мир"}, "!"]}
        self.assertEqual(extract_text(msg), "привет мир!")

    def test_text_entities_take_priority_over_text(self):
        # `text` иногда короче/иначе отформатирован, чем text_entities —
        # используем text_entities, если он есть, как более надёжный источник.
        msg = {
            "text": "raw",
            "text_entities": [{"type": "plain", "text": "из "}, {"type": "bold", "text": "entities"}],
        }
        self.assertEqual(extract_text(msg), "из entities")

    def test_missing_text(self):
        self.assertEqual(extract_text({}), "")


class ExtractOwnMessagesTests(unittest.TestCase):
    def _chat(self, messages):
        return {"messages": messages}

    def test_filters_service_events(self):
        chat = self._chat([
            {"type": "service", "action": "invite_members", "date_unixtime": str(int(days_ago(1).timestamp())),
             "from_id": OWNER_FROM_ID, "id": 1, "text": "не должно попасть, даже если бы прошло по остальным фильтрам совсем"},
        ])
        result = extract_own_messages(chat, OWNER_ID, days_ago(90))
        self.assertEqual(result, [])

    def test_filters_by_author_and_date_window(self):
        chat = self._chat([
            {"type": "message", "date_unixtime": str(int(days_ago(1).timestamp())),
             "from_id": OWNER_FROM_ID, "id": 1, "text": "моё сообщение внутри окна дат подходящее"},
            {"type": "message", "date_unixtime": str(int(days_ago(1).timestamp())),
             "from_id": "user111", "id": 2, "text": "чужое сообщение, тоже длинное и подходящее по дате"},
            {"type": "message", "date_unixtime": str(int(days_ago(200).timestamp())),
             "from_id": OWNER_FROM_ID, "id": 3, "text": "моё, но слишком старое для текущего окна дат"},
        ])
        result = extract_own_messages(chat, OWNER_ID, days_ago(90))
        self.assertEqual([m["tg_msg_id"] for m in result], [1])

    def test_pii_cleaning_and_short_message_drop_are_applied(self):
        chat = self._chat([
            {"type": "message", "date_unixtime": str(int(days_ago(1).timestamp())),
             "from_id": OWNER_FROM_ID, "id": 1, "text": "ок"},  # короткое -> отсеется
            {"type": "message", "date_unixtime": str(int(days_ago(1).timestamp())),
             "from_id": OWNER_FROM_ID, "id": 2,
             "text": "звони мне +7 921 555-12-34 если что-то срочное"},
        ])
        result = extract_own_messages(chat, OWNER_ID, days_ago(90))
        self.assertEqual(len(result), 1)
        self.assertNotIn("921", result[0]["text"])

    def test_forward_and_reply_flags(self):
        chat = self._chat([
            {"type": "message", "date_unixtime": str(int(days_ago(1).timestamp())),
             "from_id": OWNER_FROM_ID, "id": 1, "forwarded_from": "Кто-то",
             "text": "переслал сюда чужое сообщение с деньгами"},
            {"type": "message", "date_unixtime": str(int(days_ago(1).timestamp())),
             "from_id": OWNER_FROM_ID, "id": 2, "reply_to_message_id": 1,
             "text": "отвечаю на сообщение выше своими словами"},
        ])
        result = extract_own_messages(chat, OWNER_ID, days_ago(90))
        by_id = {m["tg_msg_id"]: m for m in result}
        self.assertTrue(by_id[1]["is_forward"])
        self.assertFalse(by_id[1]["is_reply"])
        self.assertFalse(by_id[2]["is_forward"])
        self.assertTrue(by_id[2]["is_reply"])

    def test_iso_date_fallback_when_no_unixtime(self):
        iso = (NOW - timedelta(days=1)).replace(microsecond=0).isoformat()
        chat = self._chat([
            {"type": "message", "date": iso, "from_id": OWNER_FROM_ID, "id": 1,
             "text": "сообщение с датой в iso-формате без unixtime"},
        ])
        result = extract_own_messages(chat, OWNER_ID, days_ago(90))
        self.assertEqual(len(result), 1)


class ExtractSubscriptionMetaTests(unittest.TestCase):
    def test_username_and_about_are_always_none(self):
        # Ключевое отличие от live-режима: экспорт не содержит username/about,
        # поэтому сверка с trusted_channels для импорт-режима невозможна.
        data = extract_subscription_meta({"name": "Какой-то канал"})
        self.assertEqual(data, {"channel_name": "Какой-то канал", "username": None, "about": None})


if __name__ == "__main__":
    unittest.main()
