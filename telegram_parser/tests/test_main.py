"""Integration tests for telegram_parser.main — full orchestration flow
against fake `telethon` and `asyncpg` (tests/_stubs), no real network or
Postgres involved.
"""
import io
import json
import os
import sys
import unittest
from datetime import datetime, timedelta, timezone

_HERE = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(_HERE, "_stubs"))
sys.path.insert(0, os.path.join(_HERE, ".."))

os.environ.setdefault("DATABASE_URL", "postgresql://fake/fake")

import asyncpg  # fake, from tests/_stubs  # noqa: E402
import telethon  # fake, from tests/_stubs  # noqa: E402

from telegram_parser import main as parser_main  # noqa: E402

NOW = datetime.now(timezone.utc)


def days_ago(n):
    return NOW - timedelta(days=n)


class ParserMainTests(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        asyncpg.reset_db()
        telethon.SCENARIO.update({
            "authorized": True,
            "me_id": 5270187642,  # реальный тип ID, каким он бывает у настоящих аккаунтов
            "entities": {},
            "messages": {},
            "about": {},
            "no_full_channel": {},
            "flood": {},
            "raise_on_entity": {},
            "get_dialogs_calls": 0,
        })

    async def _run(self, chat_ids):
        payload = {
            "session_string": "s", "api_id": 1, "api_hash": "h",
            "chat_ids": chat_ids,
        }
        sys.stdin = io.StringIO(json.dumps(payload))
        return await parser_main.main()

    async def test_user_id_comes_from_me_not_from_caller(self):
        # Ключевой момент из запроса: user_id никогда не берётся из входных
        # данных (там его вообще нет) — только из авторизованного me.id.
        telethon.SCENARIO["entities"][1001] = telethon.Entity(1001, first_name="Друг")
        telethon.SCENARIO["messages"][1001] = [
            telethon.Msg(1, days_ago(1), telethon.SCENARIO["me_id"], "тестовое сообщение"),
        ]
        await self._run([1001])
        msg = asyncpg.DB["messages"][0]
        self.assertEqual(msg["user_id"], 5270187642)

    async def test_short_messages_are_kept_no_min_words_filter(self):
        telethon.SCENARIO["entities"][1001] = telethon.Entity(1001, first_name="Друг")
        telethon.SCENARIO["messages"][1001] = [
            telethon.Msg(1, days_ago(1), telethon.SCENARIO["me_id"], "ок"),
        ]
        await self._run([1001])
        self.assertEqual(len(asyncpg.DB["messages"]), 1)
        self.assertEqual(asyncpg.DB["messages"][0]["text"], "ок")

    async def test_personal_chat_own_messages_and_no_subscription(self):
        me_id = telethon.SCENARIO["me_id"]
        telethon.SCENARIO["entities"][1001] = telethon.Entity(1001, first_name="Друг")
        telethon.SCENARIO["messages"][1001] = [
            telethon.Msg(10, days_ago(1), me_id, "у меня всё стабильно с работой сейчас"),
            telethon.Msg(9, days_ago(1), 111, "чужое сообщение в этом же чате"),
            telethon.Msg(8, days_ago(5), me_id, "три месяца назад были проблемы", forward=object()),
        ]

        code = await self._run([1001])
        self.assertEqual(code, 0)

        ids = sorted(m["tg_msg_id"] for m in asyncpg.DB["messages"])
        self.assertEqual(ids, [8, 10])  # чужое (9) отфильтровано
        self.assertEqual(asyncpg.DB["subscriptions"], {})  # личный чат — не подписка
        self.assertEqual(asyncpg.DB["parse_state"][(me_id, 1001)]["status"], "success")

    async def test_channel_subscription_matched_to_trusted(self):
        me_id = telethon.SCENARIO["me_id"]
        telethon.SCENARIO["entities"][2001] = telethon.Entity(
            2001, title="Финансы", username="fin_channel_test"
        )
        telethon.SCENARIO["about"][2001] = "Про личные финансы"
        telethon.SCENARIO["messages"][2001] = []
        asyncpg.DB["trusted_channels"]["fin_channel_test"] = 777

        code = await self._run([2001])
        self.assertEqual(code, 0)

        sub = asyncpg.DB["subscriptions"][(me_id, 2001)]
        self.assertEqual(sub["trusted_channel_id"], 777)
        self.assertEqual(sub["username"], "fin_channel_test")

    async def test_both_extractions_attempted_for_same_chat(self):
        # Ключевой сценарий: приватная группа/канал, где юзер технически
        # "подписчик", но реально пишет сам — обе выборки срабатывают сразу,
        # без ручной классификации own_messages/subscription.
        me_id = telethon.SCENARIO["me_id"]
        telethon.SCENARIO["entities"][3001] = telethon.Entity(3001, title="Своя группа")
        telethon.SCENARIO["messages"][3001] = [
            telethon.Msg(1, days_ago(1), me_id, "пишу сюда сам, хотя это как бы подписка"),
        ]
        await self._run([3001])
        self.assertEqual(len(asyncpg.DB["messages"]), 1)
        self.assertIn((me_id, 3001), asyncpg.DB["subscriptions"])  # title есть -> подписка тоже пишется

    async def test_entity_failure_does_not_block_other_chats(self):
        me_id = telethon.SCENARIO["me_id"]
        telethon.SCENARIO["raise_on_entity"][9999] = RuntimeError("CHAT_ID_INVALID")
        telethon.SCENARIO["entities"][1001] = telethon.Entity(1001, first_name="Друг")
        telethon.SCENARIO["messages"][1001] = [
            telethon.Msg(1, days_ago(1), me_id, "это сообщение должно нормально дойти"),
        ]

        code = await self._run([9999, 1001])
        self.assertEqual(code, 0)
        self.assertEqual(asyncpg.DB["parse_state"][(me_id, 9999)]["status"], "failed")
        self.assertIn("entity", asyncpg.DB["parse_state"][(me_id, 9999)]["error_message"])
        self.assertEqual(asyncpg.DB["parse_state"][(me_id, 1001)]["status"], "success")
        self.assertEqual(len(asyncpg.DB["messages"]), 1)

    async def test_flood_wait_is_retried_once_and_succeeds(self):
        me_id = telethon.SCENARIO["me_id"]
        telethon.SCENARIO["entities"][1001] = telethon.Entity(1001, first_name="Друг")
        telethon.SCENARIO["messages"][1001] = [
            telethon.Msg(1, days_ago(1), me_id, "сообщение после успешного повтора"),
        ]
        telethon.SCENARIO["flood"][1001] = {"seconds": 0, "times": 1}

        await self._run([1001])
        self.assertEqual(asyncpg.DB["parse_state"][(me_id, 1001)]["status"], "success")
        self.assertEqual(len(asyncpg.DB["messages"]), 1)

    async def test_flood_wait_persisting_marks_chat_failed(self):
        me_id = telethon.SCENARIO["me_id"]
        telethon.SCENARIO["entities"][1001] = telethon.Entity(1001, first_name="Друг")
        telethon.SCENARIO["messages"][1001] = []
        telethon.SCENARIO["flood"][1001] = {"seconds": 0, "times": 99}

        code = await self._run([1001])
        self.assertEqual(code, 0)  # один упавший чат не валит весь процесс
        state = asyncpg.DB["parse_state"][(me_id, 1001)]
        self.assertEqual(state["status"], "failed")
        self.assertIn("flood wait", state["error_message"])

    async def test_unauthorized_session_short_circuits(self):
        telethon.SCENARIO["authorized"] = False
        code = await self._run([1001])
        self.assertEqual(code, 1)
        self.assertEqual(asyncpg.DB["messages"], [])
        self.assertEqual(asyncpg.DB["ai_queue"], [])

    async def test_get_dialogs_is_called_before_parsing(self):
        telethon.SCENARIO["entities"][1001] = telethon.Entity(1001, first_name="Друг")
        telethon.SCENARIO["messages"][1001] = []
        await self._run([1001])
        self.assertEqual(telethon.SCENARIO["get_dialogs_calls"], 1)

    async def test_ai_queue_enqueued_on_success(self):
        me_id = telethon.SCENARIO["me_id"]
        telethon.SCENARIO["entities"][1001] = telethon.Entity(1001, first_name="Друг")
        telethon.SCENARIO["messages"][1001] = []
        await self._run([1001])
        self.assertEqual(asyncpg.DB["ai_queue"][0]["user_id"], me_id)
        self.assertEqual(asyncpg.DB["ai_queue"][0]["status"], "pending")


if __name__ == "__main__":
    unittest.main()
