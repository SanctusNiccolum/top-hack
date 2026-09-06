"""In-memory fake for asyncpg, just enough surface to run telegram_parser's
db.py against something without a real Postgres instance.
"""

DB = {
    "messages": [],          # list of dict rows
    "subscriptions": {},     # (user_id, chat_id) -> dict row
    "parse_state": {},       # (user_id, chat_id) -> dict row
    "ai_queue": [],          # list of dict rows
    "trusted_channels": {},  # username -> dict row
}


def reset_db():
    DB["messages"].clear()
    DB["subscriptions"].clear()
    DB["parse_state"].clear()
    DB["ai_queue"].clear()
    DB["trusted_channels"].clear()


def _norm(q: str) -> str:
    return " ".join(q.split())


class Pool:
    def acquire(self):
        return _ConnCtx()

    async def close(self):
        pass


class _ConnCtx:
    async def __aenter__(self):
        return Conn()

    async def __aexit__(self, exc_type, exc, tb):
        return False


class Conn:
    async def fetchval(self, query, *args):
        q = _norm(query)
        if "FROM parse_state" in q:
            user_id, chat_id = args
            row = DB["parse_state"].get((user_id, chat_id))
            return row["last_parsed_at"] if row else None
        if "FROM trusted_channels" in q:
            (username,) = args
            row = DB["trusted_channels"].get(username)
            return row["trusted_channel_id"] if row else None
        raise NotImplementedError(q)

    async def execute(self, query, *args):
        q = _norm(query)
        if "INSERT INTO subscriptions" in q:
            user_id, chat_id, channel_name, username, about, trusted_id = args
            DB["subscriptions"][(user_id, chat_id)] = dict(
                user_id=user_id, chat_id=chat_id, channel_name=channel_name,
                username=username, about=about, trusted_channel_id=trusted_id,
            )
        elif "INSERT INTO parse_state" in q:
            user_id, chat_id, last_parsed_at, status, error_message = args
            existing = DB["parse_state"].get((user_id, chat_id), {})
            new_last = last_parsed_at if last_parsed_at is not None else existing.get("last_parsed_at")
            DB["parse_state"][(user_id, chat_id)] = dict(
                user_id=user_id, chat_id=chat_id, last_parsed_at=new_last,
                status=status, error_message=error_message,
            )
        elif "INSERT INTO ai_queue" in q:
            user_id, status, error_message = args
            DB["ai_queue"].append(dict(user_id=user_id, status=status, error_message=error_message))
        else:
            raise NotImplementedError(q)

    async def executemany(self, query, rows):
        q = _norm(query)
        if "INSERT INTO messages" in q:
            for row in rows:
                tg_msg_id, user_id, chat_id, chat_name, chat_type, dt, text, is_forward, is_reply = row
                dup = any(
                    m["chat_id"] == chat_id and m["tg_msg_id"] == tg_msg_id
                    for m in DB["messages"]
                )
                if dup:
                    continue  # ON CONFLICT (chat_id, tg_msg_id) DO NOTHING
                DB["messages"].append(dict(
                    tg_msg_id=tg_msg_id, user_id=user_id, chat_id=chat_id,
                    chat_name=chat_name, chat_type=chat_type, datetime=dt,
                    text=text, is_forward=is_forward, is_reply=is_reply,
                ))
        else:
            raise NotImplementedError(q)


async def create_pool(dsn, min_size=1, max_size=4):
    return Pool()
