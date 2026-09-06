"""Fake in-memory stand-in for asyncpg — no real Postgres involved.

Matches SQL by substring (good enough for the handful of fixed queries in
db.py — not a real SQL engine). Reset DB state between tests with
reset_db().
"""

DB = {
    "messages": [],           # list[dict]
    "subscriptions": {},      # (user_id, chat_id) -> dict
    "parse_state": {},        # (user_id, chat_id) -> dict
    "ai_queue": [],           # list[dict]
    "trusted_channels": {},   # username -> trusted_channel_id
}


def reset_db():
    DB["messages"].clear()
    DB["subscriptions"].clear()
    DB["parse_state"].clear()
    DB["ai_queue"].clear()
    DB["trusted_channels"].clear()


class Record(dict):
    """dict that also supports Record["col"] like asyncpg.Record does — a
    plain dict already supports that, this alias just documents intent.
    """


class FakeConnection:
    async def fetchval(self, sql, *args):
        sql_l = sql.lower()
        if "from parse_state" in sql_l:
            user_id, chat_id = args
            row = DB["parse_state"].get((user_id, chat_id))
            return row["last_parsed_at"] if row else None
        if "from trusted_channels" in sql_l:
            (username,) = args
            return DB["trusted_channels"].get(username)
        raise NotImplementedError(sql)

    async def fetch(self, sql, *args):
        sql_l = sql.lower()
        if "from messages" in sql_l:
            (user_id,) = args
            rows = [m for m in DB["messages"] if m["user_id"] == user_id]
            rows.sort(key=lambda m: (m["chat_id"], m["tg_msg_id"]))
            return [Record(text=r["text"]) for r in rows]
        raise NotImplementedError(sql)

    async def fetchrow(self, sql, *args):
        raise NotImplementedError(sql)

    async def executemany(self, sql, rows):
        sql_l = sql.lower()
        if "insert into messages" in sql_l:
            existing = {(m["chat_id"], m["tg_msg_id"]) for m in DB["messages"]}
            for (tg_msg_id, user_id, chat_id, chat_name, chat_type,
                 dt, text, is_forward, is_reply) in rows:
                if (chat_id, tg_msg_id) in existing:
                    continue  # ON CONFLICT DO NOTHING
                DB["messages"].append({
                    "tg_msg_id": tg_msg_id, "user_id": user_id, "chat_id": chat_id,
                    "chat_name": chat_name, "chat_type": chat_type, "datetime": dt,
                    "text": text, "is_forward": is_forward, "is_reply": is_reply,
                })
            return
        raise NotImplementedError(sql)

    async def execute(self, sql, *args):
        sql_l = sql.lower()

        if "insert into subscriptions" in sql_l:
            user_id, chat_id, channel_name, username, about, trusted_id = args
            DB["subscriptions"][(user_id, chat_id)] = {
                "channel_name": channel_name, "username": username,
                "about": about, "trusted_channel_id": trusted_id,
            }
            return

        if "insert into parse_state" in sql_l:
            user_id, chat_id, last_parsed_at, status, error_message = args
            existing = DB["parse_state"].get((user_id, chat_id), {})
            DB["parse_state"][(user_id, chat_id)] = {
                "last_parsed_at": last_parsed_at or existing.get("last_parsed_at"),
                "status": status,
                "error_message": error_message,
            }
            return

        if "insert into ai_queue" in sql_l:
            user_id, status, error_message = args
            DB["ai_queue"].append({"user_id": user_id, "status": status, "error_message": error_message})
            return

        raise NotImplementedError(sql)


class _AcquireCtx:
    async def __aenter__(self):
        return FakeConnection()

    async def __aexit__(self, *exc):
        return False


class FakePool:
    def acquire(self):
        return _AcquireCtx()

    async def close(self):
        pass


async def create_pool(dsn, min_size=1, max_size=4):
    return FakePool()


class Pool:  # только для аннотаций типов в db.py (asyncpg.Pool)
    pass
