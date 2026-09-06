"""Интеграционные тесты для main_import.py (режим без Telegram API).
Фейковый asyncpg + временный result.json на диске — ни Telegram, ни
реальный Postgres не задействованы.
"""
import io
import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone

_HERE = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(_HERE, "_stubs"))
sys.path.insert(0, os.path.join(_HERE, ".."))

os.environ.setdefault("DATABASE_URL", "postgresql://fake/fake")

import asyncpg  # fake, from tests/_stubs  # noqa: E402

from telegram_parser import main_import as parser_main_import  # noqa: E402

NOW = datetime.now(timezone.utc)
OWNER_TG_ID = 5270187642  # реальный тип ID


def days_ago(n):
    return NOW - timedelta(days=n)


def _write_export(tmp_dir, chats) -> str:
    export = {
        "personal_information": {"user_id": OWNER_TG_ID, "first_name": "Тест"},
        "chats": {"list": chats},
    }
    path = os.path.join(tmp_dir, "result.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(export, f, ensure_ascii=False)
    return path


class MainImportTests(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        asyncpg.reset_db()
        self._tmpdir = tempfile.TemporaryDirectory()

    def tearDown(self):
        self._tmpdir.cleanup()

    async def _run(self, payload):
        sys.stdin = io.StringIO(json.dumps(payload))
        return await parser_main_import.main()

    async def test_user_id_comes_from_export_not_placeholder(self):
        export_path = _write_export(self._tmpdir.name, [
            {"id": 1001, "type": "personal_chat", "name": "Друг", "messages": [
                {"type": "message", "id": 1, "from_id": f"user{OWNER_TG_ID}",
                 "date_unixtime": str(int(days_ago(1).timestamp())), "text": "тест"},
            ]},
        ])
        await self._run({"export_path": export_path, "chat_ids": [1001]})
        self.assertEqual(asyncpg.DB["messages"][0]["user_id"], OWNER_TG_ID)

    async def test_personal_chat_own_messages_end_to_end(self):
        export_path = _write_export(self._tmpdir.name, [
            {"id": 1001, "type": "personal_chat", "name": "Друг", "messages": [
                {"type": "message", "id": 1, "from_id": f"user{OWNER_TG_ID}",
                 "date_unixtime": str(int(days_ago(1).timestamp())), "text": "моё сообщение"},
                {"type": "message", "id": 2, "from_id": "user111",
                 "date_unixtime": str(int(days_ago(1).timestamp())), "text": "чужое сообщение"},
            ]},
        ])
        code = await self._run({"export_path": export_path, "chat_ids": [1001]})
        self.assertEqual(code, 0)

        ids = {m["tg_msg_id"] for m in asyncpg.DB["messages"]}
        self.assertEqual(ids, {1})
        self.assertEqual(asyncpg.DB["parse_state"][(OWNER_TG_ID, 1001)]["status"], "success")
        self.assertEqual(asyncpg.DB["ai_queue"][0]["status"], "pending")

    async def test_channel_becomes_subscription_without_username(self):
        export_path = _write_export(self._tmpdir.name, [
            {"id": 2001, "type": "public_channel", "name": "Финансы для всех"},
        ])
        await self._run({"export_path": export_path, "chat_ids": [2001]})

        sub = asyncpg.DB["subscriptions"][(OWNER_TG_ID, 2001)]
        self.assertEqual(sub["channel_name"], "Финансы для всех")
        self.assertIsNone(sub["username"])
        self.assertIsNone(sub["trusted_channel_id"])  # сверка невозможна без username

    async def test_requested_chat_id_missing_from_export(self):
        export_path = _write_export(self._tmpdir.name, [
            {"id": 1001, "type": "personal_chat", "name": "Друг", "messages": []},
        ])
        code = await self._run({"export_path": export_path, "chat_ids": [9999999]})
        self.assertEqual(code, 0)  # отсутствие одного чата не должно валить весь запуск
        state = asyncpg.DB["parse_state"][(OWNER_TG_ID, 9999999)]
        self.assertEqual(state["status"], "failed")
        self.assertIn("не найден", state["error_message"])

    async def test_one_chat_failing_does_not_block_others(self):
        export_path = _write_export(self._tmpdir.name, [
            {"id": 1001, "type": "personal_chat", "name": "Друг", "messages": [
                {"type": "message", "id": 1, "from_id": f"user{OWNER_TG_ID}",
                 "date_unixtime": str(int(days_ago(1).timestamp())), "text": "должно дойти"},
            ]},
        ])
        code = await self._run({"export_path": export_path, "chat_ids": [9999999, 1001]})
        self.assertEqual(code, 0)
        self.assertEqual(asyncpg.DB["parse_state"][(OWNER_TG_ID, 9999999)]["status"], "failed")
        self.assertEqual(asyncpg.DB["parse_state"][(OWNER_TG_ID, 1001)]["status"], "success")

    async def test_missing_export_file(self):
        code = await self._run({"export_path": "/nonexistent/result.json", "chat_ids": [1001]})
        self.assertEqual(code, 1)

    async def test_missing_personal_information(self):
        path = os.path.join(self._tmpdir.name, "result.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"chats": {"list": []}}, f)
        code = await self._run({"export_path": path, "chat_ids": []})
        self.assertEqual(code, 1)


if __name__ == "__main__":
    unittest.main()
