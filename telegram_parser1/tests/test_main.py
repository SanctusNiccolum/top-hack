"""Integration tests for the parser subprocess's orchestration logic
(main.py), against fake telethon/asyncpg stand-ins under tests/_stubs.

These do NOT touch a real Telegram account or a real Postgres instance —
they exercise the parser's own control flow: per-chat error isolation,
flood-wait retry, own-message filtering, subscription matching, and the
final ai_queue signal. See README's "Известные ограничения MVP" — this
closes that gap for the parts that can be tested without a live account;
a real session_string is still needed before production use.
"""
import sys
import os
import io
import json
import unittest
from datetime import datetime, timedelta, timezone

_HERE = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(_HERE, "_stubs"))
sys.path.insert(0, os.path.join(_HERE, ".."))

os.environ.setdefault("DATABASE_URL", "postgresql://fake/fake")

import telethon  # fake, from tests/_stubs
import asyncpg   # fake, from tests/_stubs

from telegram_parser import main as parser_main

NOW = datetime.now(timezone.utc)


def days_ago(n):
    return NOW - timedelta(days=n)


class ParserMainTests(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        asyncpg.reset_db()
        telethon.SCENARIO.clear()
        telethon.SCENARIO.update({
            "authorized": True,
            "me_id": 999,
            "entities": {},
            "messages": {},
            "about": {},
            "no_full_channel": {},
            "flood": {},
            "raise_on_entity": {},
            "get_dialogs_calls": 0,
        })

    async def _run(self, payload):
        sys.stdin = io.StringIO(json.dumps(payload))
        return await parser_main.main()

    async def test_own_messages_filtered_and_forward_flagged(self):
        telethon.SCENARIO["entities"][1001] = telethon.Entity(1001, title="Мой чат")
        telethon.SCENARIO["messages"][1001] = [
            telethon.Msg(106, None, 999, "сообщение без даты (должно быть пропущено)"),
            telethon.Msg(105, days_ago(1), 999, "Работаю над новым проектом для клиента"),
            telethon.Msg(104, days_ago(2), 111, "чужое сообщение — не должно попасть в выборку"),
            telethon.Msg(103, days_ago(3), 999, "ок"),  # too short, dropped
            telethon.Msg(101, days_ago(5), 999, "Репост новости про биткоин заработок",
                         forward=object()),
            telethon.Msg(100, days_ago(95), 999, "слишком старое сообщение вне окна"),
        ]
        payload = {
            "user_id": 42, "session_string": "s", "api_id": 1, "api_hash": "h",
            "chats": [{"chat_id": 1001, "type": "own_messages"}],
        }
        code = await self._run(payload)
        self.assertEqual(code, 0)

        stored = {m["tg_msg_id"]: m for m in asyncpg.DB["messages"]}
        self.assertEqual(set(stored), {105, 101})
        self.assertFalse(stored[105]["is_forward"])
        self.assertTrue(stored[101]["is_forward"])
        self.assertEqual(asyncpg.DB["parse_state"][(42, 1001)]["status"], "success")

    async def test_subscription_matches_trusted_channel(self):
        telethon.SCENARIO["entities"][2001] = telethon.Entity(
            2001, title="Финансовые сигналы", username="finance_signals")
        telethon.SCENARIO["about"][2001] = "Инвестиции и трейдинг"
        asyncpg.DB["trusted_channels"]["finance_signals"] = {
            "trusted_channel_id": 55, "category": "finance"}

        payload = {
            "user_id": 42, "session_string": "s", "api_id": 1, "api_hash": "h",
            "chats": [{"chat_id": 2001, "type": "subscription"}],
        }
        await self._run(payload)

        sub = asyncpg.DB["subscriptions"][(42, 2001)]
        self.assertEqual(sub["trusted_channel_id"], 55)
        self.assertEqual(sub["username"], "finance_signals")

    async def test_subscription_without_username_has_no_trusted_match(self):
        telethon.SCENARIO["entities"][2002] = telethon.Entity(
            2002, title="Приватный канал", username=None)
        telethon.SCENARIO["no_full_channel"][2002] = True  # GetFullChannelRequest fails

        payload = {
            "user_id": 42, "session_string": "s", "api_id": 1, "api_hash": "h",
            "chats": [{"chat_id": 2002, "type": "subscription"}],
        }
        code = await self._run(payload)
        self.assertEqual(code, 0)  # a failing GetFullChannelRequest must not fail the chat

        sub = asyncpg.DB["subscriptions"][(42, 2002)]
        self.assertIsNone(sub["trusted_channel_id"])
        self.assertIsNone(sub["about"])

    async def test_one_chat_failing_does_not_block_the_others(self):
        telethon.SCENARIO["raise_on_entity"][1002] = RuntimeError("PEER_ID_INVALID")
        telethon.SCENARIO["entities"][1003] = telethon.Entity(1003, title="OK-чат")
        telethon.SCENARIO["messages"][1003] = [
            telethon.Msg(1, days_ago(1), 999, "это сообщение должно дойти до базы данных"),
        ]
        payload = {
            "user_id": 42, "session_string": "s", "api_id": 1, "api_hash": "h",
            "chats": [
                {"chat_id": 1002, "type": "own_messages"},
                {"chat_id": 1003, "type": "own_messages"},
            ],
        }
        code = await self._run(payload)
        self.assertEqual(code, 0)

        self.assertEqual(asyncpg.DB["parse_state"][(42, 1002)]["status"], "failed")
        self.assertEqual(asyncpg.DB["parse_state"][(42, 1003)]["status"], "success")
        self.assertEqual(len(asyncpg.DB["ai_queue"]), 1)
        self.assertEqual(asyncpg.DB["ai_queue"][0]["status"], "pending")

    async def test_flood_wait_is_retried_once_and_succeeds(self):
        telethon.SCENARIO["entities"][1003] = telethon.Entity(1003, title="Flood chat")
        telethon.SCENARIO["messages"][1003] = [
            telethon.Msg(1, days_ago(1), 999, "сообщение после успешного повтора запроса"),
        ]
        telethon.SCENARIO["flood"][1003] = {"seconds": 0, "times": 1}

        payload = {
            "user_id": 42, "session_string": "s", "api_id": 1, "api_hash": "h",
            "chats": [{"chat_id": 1003, "type": "own_messages"}],
        }
        code = await self._run(payload)
        self.assertEqual(code, 0)
        self.assertEqual(asyncpg.DB["parse_state"][(42, 1003)]["status"], "success")
        self.assertEqual(len(asyncpg.DB["messages"]), 1)

    async def test_flood_wait_persisting_marks_chat_failed(self):
        telethon.SCENARIO["entities"][1003] = telethon.Entity(1003, title="Flood chat")
        telethon.SCENARIO["messages"][1003] = []
        telethon.SCENARIO["flood"][1003] = {"seconds": 0, "times": 99}  # never recovers

        payload = {
            "user_id": 42, "session_string": "s", "api_id": 1, "api_hash": "h",
            "chats": [{"chat_id": 1003, "type": "own_messages"}],
        }
        await self._run(payload)
        state = asyncpg.DB["parse_state"][(42, 1003)]
        self.assertEqual(state["status"], "failed")
        self.assertIn("flood wait", state["error_message"])

    async def test_get_dialogs_is_called_before_parsing(self):
        # Regression test for the "Could not find the input entity" bug:
        # StringSession carries no entity cache across processes, so
        # main() must call get_dialogs() once to warm it up before trying
        # to resolve any chat_id. If this assertion ever fails, real runs
        # will break on personal chats/groups exactly like they did before
        # this fix, even though every other test here still passes (the
        # fake get_entity doesn't model the cache-miss behavior at all).
        telethon.SCENARIO["entities"][1001] = telethon.Entity(1001, title="Мой чат")
        telethon.SCENARIO["messages"][1001] = []
        payload = {
            "user_id": 42, "session_string": "s", "api_id": 1, "api_hash": "h",
            "chats": [{"chat_id": 1001, "type": "own_messages"}],
        }
        await self._run(payload)
        self.assertEqual(telethon.SCENARIO["get_dialogs_calls"], 1)

    async def test_unauthorized_session_short_circuits(self):
        telethon.SCENARIO["authorized"] = False
        payload = {
            "user_id": 42, "session_string": "bad", "api_id": 1, "api_hash": "h",
            "chats": [{"chat_id": 1001, "type": "own_messages"}],
        }
        code = await self._run(payload)
        self.assertEqual(code, 1)
        self.assertEqual(asyncpg.DB["messages"], [])
        self.assertEqual(asyncpg.DB["parse_state"], {})
        self.assertEqual(asyncpg.DB["ai_queue"][0]["status"], "failed")


if __name__ == "__main__":
    unittest.main()
